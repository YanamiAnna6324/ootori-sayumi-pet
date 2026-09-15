# Ootori Sayumi pet

正在把提供的 Sayumi 插画制作成 Codex 桌面宠物。第一张图只作为待机模板，其他图片分别提供动作、表情和服装参考。

## 查看本次修复

直接打开 [透明素材预览](outputs/ootori_sayumi_pet/cutouts-v4/preview.html)。页面可切换七张素材、深浅背景与棋盘，并拖动角色检查轮廓。也可查看 [深浅背景对照](outputs/ootori_sayumi_pet/cutouts-v4/light-dark-qa.png)。

本次修复保留原图像素，处理透明背景、白衣和发丝缺失、双人图的右侧人物、贴纸外框与额外裁剪。每张图的截断和装饰残留记录在 [素材报告](outputs/ootori_sayumi_pet/cutouts-v4/extraction-report.json)。

## 当前状态

目前是透明素材检查版本，**完整的 Codex v2 动画包尚未通过验收**。部分原图本身是半身图，惊讶符号和心形气泡也遮住了发丝，需要补画；尚缺真实动作循环和十六个视线方向。旧 atlas、旧状态条和旧 QA 文件保留用于调试，不能视为本次重做成品。

完整 v2 需要九个标准动作和十六个视线方向，8×11 格、每格 192×208，总尺寸 1536×2288。第 0 行第 6 列为 neutral frame。进食、睡眠可额外保留为预览动作；Codex 不会读取 `state-map.json` 自动增加原生状态。

[动作与参考图计划](work/repair-v4/generation-plan.json) 和 [补画要求](work/repair-v4/generation-prompt.md) 已准备好。当前会话没有内置图像生成工具，API Key 也未配置；补画尚未执行。

## 安装器

`install-pet.ps1` 已修复 PowerShell 语法，读取源清单，支持 `-Destination`，以 UTF-8 无 BOM 写入安装清单。`release-status.json` 当前标为不可安装，因此它会保留现有客户端宠物并提示重做包未就绪。通过结构和视觉验收后才能更新发布状态。

安装器验证：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File tests/test-installer.ps1
```

测试仅使用 `work/installer-test-*` 临时目录，不改动真实 `.codex/pets`。全部临时文件按用户要求保留。

## 重新提取素材

```powershell
python work/extract_cutouts_v4.py
```

需要 Pillow、NumPy、OpenCV、rembg、ONNX Runtime 与本机已缓存的 U2Net 权重。默认读取 `C:\Users\HP\Downloads\codex宠物`。此步骤只抠图，不生成缺失身体或动画。
