# 模型文件下载说明

本目录需要放置 Wav2Lip 模型权重文件。由于文件过大，未包含在 Git 仓库中。

## 下载链接

请下载以下模型文件并放置到此目录：

### 必需文件

1. **wav2lip_gan.pth** (436MB)
   - Hugging Face: https://huggingface.co/Nekochu/Wav2Lip/resolve/main/wav2lip_gan.pth
   - 备用地址: https://huggingface.co/numz/wav2lip_studio/resolve/main/checkpoints/wav2lip_gan.pth
   - GitHub (Google Drive): https://github.com/Rudrabha/Wav2Lip (查看 README 中的 Google Drive 链接)

### 可选文件

2. **SadTalker_V0.0.2_256.safetensors** (725MB)
   - 用于更高质量的唇形同步
   - Hugging Face: https://huggingface.co/TonyD2046/sadtalker-01/resolve/main/SadTalker_V0.0.2_256.safetensors
   - GitHub: https://github.com/OpenTalker/SadTalker

3. **wav2lipv2.pth** (205MB)
   - Wav2Lip v2 版本模型
   - 请从 Wav2Lip 相关仓库获取

## 文件结构

下载完成后，目录结构应该是：

```
backend/checkpoints/
├── README.md (本文件)
├── wav2lip_gan.pth
├── SadTalker_V0.0.2_256.safetensors (可选)
└── wav2lipv2.pth (可选)
```
