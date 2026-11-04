# 运行环境与格式

代码与机器环境分离。preflight.py 按 PHOTO3D_RUNTIME 环境变量、技能根目录 runtime.local.json、默认 ~/.codex/cache/photo-to-3d-diorama/v1 查找环境。配置、依赖和权重不上传 GitHub。

install_runtime.py --python-root <Python目录> --packages <依赖目录> --source <官方代码目录> --weights <权重目录> --blender-root <可选Blender目录> --cache-root <稳定缓存目录> 可复用本机已验证环境。同盘硬链接，失败复制，不使用指向旧项目的目录链接；删除旧项目不会破坏已迁移文件。

新电脑需准备相容 Python、PyTorch/CUDA、torchvision、numpy、Pillow、safetensors、tqdm，以及官方 TripoSplat 代码和五个权重。安装脚本不自动下载、登录或消费。官方代码 https://github.com/VAST-AI-Research/TripoSplat ，模型 https://huggingface.co/VAST-AI/TripoSplat 。遵守各自许可证。

本地推理分阶段搬运编码器、流模型和解码器到 GPU 以适配8GB显存。默认 seed=42、steps=20、guidance=3、gaussians=262144。OOM 停止报告，不静默换收费服务。

| 文件 | 含义 |
|---|---|
| model.ply | 完整各向异性三维高斯参数；不是三角网格 |
| model.splat | 每点32字节网页高斯格式，颜色及旋转量化 |
| preview.html | 内嵌模型及渲染库，可离线旋转，无外部CDN |
| model.blend | 可选，完整参数及抽样椭球代理，代理不等于透明高斯最终画质 |
| .glb/.gltf | 网格、骨骼、碰撞需求须另走实际网格重建，不能换后缀冒充 |

PLY 使用官方默认导出坐标（内部坐标变换为 x,-z,y），预览再变换为(x,-y,-z)，正面从+X看；Blender 将 PLY 转为(x,z,-y)。单位为相对单位，真实毫米尺寸需已知参照。动画和碰撞不是重建资产自动拥有的功能。

角色网格路线不由 export_blender.py 自动完成。点云转体积、椭球代理实化或表面重建只产生待验收底稿；闭合网格仍可能有凹坑、浮粒、手指融合和材质污染。需在 Blender 实际渲染后按 production-and-review.md 排查，不能用高面数代替品质。
