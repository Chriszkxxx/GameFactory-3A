using System;
using System.Collections.Generic;
using UnityEngine;

namespace FPSExample
{
    [DisallowMultipleComponent]
    public sealed class FPSDoor : MonoBehaviour
    {
        [SerializeField] private float openDistance = 1.45f;
        [SerializeField] private float openSpeed = 3.5f;

        private Transform[] panels = Array.Empty<Transform>();
        private Vector3[] closedPositions = Array.Empty<Vector3>();
        private Vector3[] openPositions = Array.Empty<Vector3>();

        public bool IsOpen { get; private set; }
        public bool IsConfigured => panels.Length > 0;

        public event Action<FPSDoor> StateChanged;

        public bool ConfigureFromPrefab()
        {
            var uniquePanels = new HashSet<Transform>();
            foreach (BoxCollider collider in GetComponentsInChildren<BoxCollider>(true))
            {
                if (collider == null || collider.isTrigger)
                    continue;
                Vector3 size = collider.bounds.size;
                if (size.y < 1.5f || Mathf.Max(size.x, size.z) < 0.5f ||
                    Mathf.Min(size.x, size.z) > 0.75f)
                    continue;
                uniquePanels.Add(collider.transform);
            }

            var sorted = new List<Transform>(uniquePanels);
            sorted.Sort((left, right) =>
                transform.InverseTransformPoint(PanelWorldCenter(left)).x.CompareTo(
                    transform.InverseTransformPoint(PanelWorldCenter(right)).x));
            if (sorted.Count > 2)
                sorted = sorted.GetRange(0, 2);
            if (sorted.Count == 0)
            {
                enabled = false;
                return false;
            }

            panels = sorted.ToArray();
            closedPositions = new Vector3[panels.Length];
            openPositions = new Vector3[panels.Length];
            Vector3 doorwayCenter = Vector3.zero;
            foreach (Transform panel in panels)
                doorwayCenter += PanelWorldCenter(panel);
            doorwayCenter /= panels.Length;

            for (int index = 0; index < panels.Length; index++)
            {
                Transform panel = panels[index];
                closedPositions[index] = panel.localPosition;
                Vector3 worldDirection = Vector3.ProjectOnPlane(
                    PanelWorldCenter(panel) - doorwayCenter,
                    transform.up).normalized;
                if (worldDirection.sqrMagnitude < 0.0001f)
                    worldDirection = transform.right * (index == 0 ? -1f : 1f);
                Vector3 localDirection = panel.parent != null
                    ? panel.parent.InverseTransformDirection(worldDirection).normalized
                    : worldDirection.normalized;
                openPositions[index] = closedPositions[index] + localDirection * openDistance;
            }
            return true;
        }

        public void Toggle()
        {
            SetOpen(!IsOpen, false);
        }

        public void SetOpen(bool open, bool immediate)
        {
            if (!IsConfigured)
                return;
            IsOpen = open;
            SetPanelCollidersEnabled(!open);
            if (immediate)
            {
                for (int index = 0; index < panels.Length; index++)
                    if (panels[index] != null)
                        panels[index].localPosition = open
                            ? openPositions[index]
                            : closedPositions[index];
            }
            Debug.Log("[FPS_DOOR] " + name + " open=" + IsOpen);
            StateChanged?.Invoke(this);
        }

        private void Update()
        {
            for (int index = 0; index < panels.Length; index++)
            {
                if (panels[index] == null)
                    continue;
                Vector3 target = IsOpen ? openPositions[index] : closedPositions[index];
                panels[index].localPosition = Vector3.MoveTowards(
                    panels[index].localPosition,
                    target,
                    Mathf.Max(0f, openSpeed) * Time.deltaTime);
            }
        }

        private static Vector3 PanelWorldCenter(Transform panel)
        {
            BoxCollider collider = panel.GetComponent<BoxCollider>();
            return collider != null ? collider.bounds.center : panel.position;
        }

        private void SetPanelCollidersEnabled(bool value)
        {
            foreach (Transform panel in panels)
            {
                if (panel == null)
                    continue;
                foreach (Collider collider in panel.GetComponentsInChildren<Collider>(true))
                    if (collider != null)
                        collider.enabled = value;
            }
        }
    }
}
