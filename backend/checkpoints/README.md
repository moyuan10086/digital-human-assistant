# 模型文件下载说明

本目录需要放置 Wav2Lip 模型权重文件。由于文件过大，未包含在 Git 仓库中。

## 下载链接

请下载以下模型文件并放置到此目录：

### 必需文件

1. **wav2lip_gan.pth** (416MB)
   - 下载地址: https://github.com/Rudrabha/Wav2Lip/releases
   - 或百度网盘: https://pan.baidu.com/s/1xXX (提取码: xxxx)

### 可选文件

2. **SadTalker_V0.0.2_256.safetensors** (692MB)
   - 用于更高质量的唇形同步
   - 下载地址: https://github.com/OpenTalker/SadTalker

3. **wav2lipv2.pth** (205MB)
   - Wav2Lip v2 版本模型

## 文件结构

下载完成后，目录结构应该是：

```
backend/checkpoints/
├── README.md (本文件)
├── wav2lip_gan.pth
├── SadTalker_V0.0.2_256.safetensors (可选)
└── wav2lipv2.pth (可选)
```
