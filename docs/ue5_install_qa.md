# 在 Linux Shell 中配置 UE5 时遇到的问题

## 启动 Editor

### 问题 1

现象：Editor 因 Vulkan 设备不满足 UE 5.7 的 SM5 Profile 而主动退出。

分析：日志中的关键信息依次为：

- 识别到 NVIDIA H800，驱动版本为 535.129.03
- 开始检查 `VP_UE_Vulkan_SM5`
- `None of the 1 devices meet all the criteria`
- `Skipping SF_VULKAN_SM5`
- `Vulkan device could not be created`
- 以返回码 1 退出

问题：UE5 要求 NVIDIA Driver 版本为 570 以上（参见[官方文档 Recommended Hardware](https://dev.epicgames.com/documentation/unreal-engine/linux-development-requirements-for-unreal-engine?lang=en-US）。因此，问题在于 NVIDIA Driver 版本过低。

解决方式：请求升级宿主机的驱动版本（但尚未得到回复）。

### 问题 2

容器不支持 NVIDIA Vulkan 图形能力。即当前配置为 `NVIDIA_DRIVER_CAPABILITIES=compute,utility`，缺少 `graphics`。

解决方式：启动机器时添加环境变量 `NVIDIA_DRIVER_CAPABILITIES=compute,utility,graphics`。但由于在第一个问题中就出现了报错，因此该方式的有效性暂未验证。
