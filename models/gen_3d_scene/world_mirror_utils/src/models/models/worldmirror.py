from typing import Dict, List

import torch
import torch.nn as nn
import torch.nn.functional as F

from models.gen_3d_scene.world_mirror_utils.src.models.models.visual_transformer import (
    VisualGeometryTransformer,
)
from models.gen_3d_scene.world_mirror_utils.src.models.heads.camera_head import (
    CameraHead,
)
from models.gen_3d_scene.world_mirror_utils.src.models.heads.dense_head import (
    DPTHead,
)
from models.gen_3d_scene.world_mirror_utils.src.models.utils.camera_utils import (
    vector_to_camera_matrices,
    extrinsics_to_vector,
)
from models.gen_3d_scene.world_mirror_utils.src.models.utils.priors import (
    normalize_depth,
    normalize_poses,
)

from huggingface_hub import PyTorchModelHubMixin


class WorldMirror(nn.Module, PyTorchModelHubMixin):
    def __init__(
        self,
        img_size=518,
        patch_size=14,
        embed_dim=1024,
        gs_dim=256,
        enable_cond=True,
        enable_cam=True,
        enable_pts=True,
        enable_depth=True,
        enable_norm=True,
        enable_gs=False,
        patch_embed="dinov2_vitl14_reg",
        fixed_patch_embed=False,
        sampling_strategy="uniform",
        dpt_gradient_checkpoint=False,
        condition_strategy=["token", "pow3r", "token"],
    ):

        super().__init__()
        # Configuration flags
        self.img_size = img_size
        self.patch_size = patch_size
        self.embed_dim = embed_dim
        self.gs_dim = gs_dim
        self.enable_cam = enable_cam
        self.enable_pts = enable_pts
        self.enable_depth = enable_depth
        self.enable_cond = enable_cond
        self.enable_norm = enable_norm
        # The Gaussian-splatting branch is not vendored; see this package's
        # README. The checkpoint config sets it, so accept and ignore the flag
        # rather than reject the config outright.
        self.enable_gs = False
        self.patch_embed = patch_embed
        self.sampling = sampling_strategy
        self.dpt_checkpoint = dpt_gradient_checkpoint
        self.cond_methods = condition_strategy
        self.config = self._store_config()

        # Visual geometry transformer
        self.visual_geometry_transformer = VisualGeometryTransformer(
            img_size=img_size,
            patch_size=patch_size,
            embed_dim=embed_dim,
            enable_cond=enable_cond,
            sampling_strategy=sampling_strategy,
            patch_embed=patch_embed,
            fixed_patch_embed=fixed_patch_embed,
            condition_strategy=condition_strategy,
        )

        # Initialize prediction heads
        self._init_heads(embed_dim, patch_size, gs_dim)

    def _store_config(self):
        """Save the model configuration."""
        return {
            "img_size": self.img_size,
            "patch_size": self.patch_size,
            "embed_dim": self.embed_dim,
            "gs_dim": self.gs_dim,
            "enable_cam": self.enable_cam,
            "enable_pts": self.enable_pts,
            "enable_depth": self.enable_depth,
            "enable_norm": self.enable_norm,
            "enable_gs": self.enable_gs,
            "patch_embed": self.patch_embed,
            "sampling_strategy": self.sampling,
            "dpt_checkpoint": self.dpt_checkpoint,
            "condition_strategy": self.cond_methods,
        }

    def _init_heads(self, dim, patch_size, gs_dim):
        """Initialize all prediction heads."""

        # Camera pose prediction head
        if self.enable_cam:
            self.cam_head = CameraHead(dim_in=2 * dim)

        # 3D point prediction head
        if self.enable_pts:
            self.pts_head = DPTHead(
                dim_in=2 * dim,
                output_dim=4,
                patch_size=patch_size,
                activation="inv_log+expp1",
            )

        # Depth prediction head
        if self.enable_depth:
            self.depth_head = DPTHead(
                dim_in=2 * dim,
                output_dim=2,
                patch_size=patch_size,
                activation="exp+expp1",
            )

        # Surface normal prediction head
        if self.enable_norm:
            self.norm_head = DPTHead(
                dim_in=2 * dim,
                output_dim=4,
                patch_size=patch_size,
                activation="norm+expp1",
            )


    def forward(
        self,
        views: Dict[str, torch.Tensor],
        cond_flags: List[int] = [0, 0, 0],
        is_inference=True,
    ):
        """Execute forward pass through the WorldMirror model.

        Args:
            views: Input data dictionary
            cond_flags: Conditioning flags [depth, rays, camera]

        Returns:
            dict: Prediction results dictionary
        """
        imgs = views["img"]

        # Enable conditional input during training if enabled, or during inference if any cond_flags are set
        use_cond = sum(cond_flags) > 0

        # Extract priors and process features based on conditional input
        if use_cond:
            priors = self.extract_priors(views)
            token_list, patch_start_idx = self.visual_geometry_transformer(
                imgs, priors, cond_flags=cond_flags
            )
        else:
            token_list, patch_start_idx = self.visual_geometry_transformer(imgs)

        # Execute predictions
        with torch.amp.autocast("cuda", dtype=torch.float32):
            # Generate all predictions
            preds = self._gen_all_preds(
                token_list,
                imgs,
                patch_start_idx,
                views,
                cond_flags,
                is_inference,
            )

        return preds

    def _gen_all_preds(
        self, token_list, imgs, patch_start_idx, views, cond_flags, is_inference
    ):
        """Generate all enabled predictions."""
        preds = {}

        # Camera pose prediction
        if self.enable_cam:
            cam_seq = self.cam_head(token_list)
            cam_params = cam_seq[-1]
            preds["camera_params"] = cam_params
            c2w_mat, int_mat = self.transform_camera_vector(
                cam_params, imgs.shape[-2], imgs.shape[-1]
            )
            preds["camera_poses"] = (
                c2w_mat  # C2W pose (OpenCV) in world coordinates: [B, S, 4, 4]
            )
            preds["camera_intrs"] = (
                int_mat  # Camera intrinsic matrix: [B, S, 3, 3]
            )

        # Depth prediction
        if self.enable_depth:
            depth, depth_conf = self.depth_head(
                token_list,
                images=imgs,
                patch_start_idx=patch_start_idx,
            )
            preds["depth"] = depth
            preds["depth_conf"] = depth_conf

        # 3D point prediction
        if self.enable_pts:
            pts, pts_conf = self.pts_head(
                token_list,
                images=imgs,
                patch_start_idx=patch_start_idx,
            )
            preds["pts3d"] = pts
            preds["pts3d_conf"] = pts_conf

        # Normal prediction
        if self.enable_norm:
            normals, norm_conf = self.norm_head(
                token_list,
                images=imgs,
                patch_start_idx=patch_start_idx,
            )
            preds["normals"] = normals
            preds["normals_conf"] = norm_conf

        return preds

    def extract_priors(self, views):
        """Extract and normalize geometric priors.

        Args:
            views: Input view data dictionary.

        Returns:
            tuple: (depths, rays, poses) Normalized priors.
        """
        h, w = views["img"].shape[-2:]

        # Initialize prior variables
        depths = rays = poses = None

        # Extract camera pose
        if "camera_poses" in views:
            extrinsics = views["camera_poses"][:, :, :3]
            extrinsics = normalize_poses(extrinsics)
            cam_params = extrinsics_to_vector(extrinsics)
            poses = cam_params[:, :, :7]  # Shape: [B, S, 7]

        # Extract depth map
        if "depthmap" in views:
            depth_h, depth_w = views["depthmap"].shape[-2:]
            depths = views["depthmap"]
            if (
                depth_h != h or depth_w != w
            ):  # Check if depth dimensions match target resolution
                try:
                    depths = F.interpolate(
                        depths,
                        size=(h, w),
                        mode="bilinear",
                        align_corners=False,
                    )
                except:
                    import pdb

                    pdb.set_trace()
            depths = normalize_depth(depths)  # Shape: [B, S, H, W]

        # Extract ray directions
        if "camera_intrs" in views:
            intrinsics = views["camera_intrs"][:, :, :3, :3]
            fx, fy = intrinsics[:, :, 0, 0] / w, intrinsics[:, :, 1, 1] / h
            cx, cy = intrinsics[:, :, 0, 2] / w, intrinsics[:, :, 1, 2] / h
            rays = torch.stack([fx, fy, cx, cy], dim=-1)  # Shape: [B, S, 4]

        return (depths, rays, poses)

    def transform_camera_vector(self, camera_params, h, w):
        ext_mat, int_mat = vector_to_camera_matrices(
            camera_params, image_hw=(h, w)
        )
        # Create homogeneous transformation matrix
        homo_row = torch.tensor([0, 0, 0, 1], device=ext_mat.device).view(
            1, 1, 1, 4
        )
        homo_row = homo_row.repeat(ext_mat.shape[0], ext_mat.shape[1], 1, 1)
        w2c_mat = torch.cat([ext_mat, homo_row], dim=2)
        c2w_mat = torch.linalg.inv(w2c_mat)
        return c2w_mat, int_mat


