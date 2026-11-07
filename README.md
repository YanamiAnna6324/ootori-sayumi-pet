# Ootori Sayumi pet

正在把提供的 Sayumi 插画制作成 Codex 桌面宠物。第一张图只作为待机模板，其他图片分别提供动作、表情和服装参考。

## 查看本次修复

最新的 [8 帧稳定待机动画](output/imagegen/repair-v5/idle-stable-v2/preview.html) 已可预览。页面对比固定身体与轻微晃动两种版本，也展示实际 192×208 帧尺寸，并支持深浅背景检查。身体来自原始待机抠图；模型只提供局部表情，腿部与脚底位置保持一致。所有帧使用同一份清理后的轮廓基准，原始白边已减轻，放大后仍有少量浅边与锯齿。

直接打开 [透明素材预览](outputs/ootori_sayumi_pet/cutouts-v4/preview.html)。页面可切换七张素材、深浅背景与棋盘，并拖动角色检查轮廓。也可查看 [深浅背景对照](outputs/ootori_sayumi_pet/cutouts-v4/light-dark-qa.png)。

本次修复保留原图像素，处理透明背景、白衣和发丝缺失、双人图的右侧人物、贴纸外框与额外裁剪。每张图的截断和装饰残留记录在 [素材报告](outputs/ootori_sayumi_pet/cutouts-v4/extraction-report.json)。

## 当前状态

目前已完成 8 帧稳定待机预览，**完整的 Codex v2 动画包尚未通过验收**。部分原图本身是半身图，惊讶符号和心形气泡也遮住了发丝，需要补画；其余动作循环和十六个视线方向仍待完成。旧 atlas、旧状态条和旧 QA 文件保留用于调试，不能视为本次重做成品。

完整 v2 需要九个标准动作和十六个视线方向，8×11 格、每格 192×208，总尺寸 1536×2288。第 0 行第 6 列为 neutral frame。进食、睡眠可额外保留为预览动作；Codex 不会读取 `state-map.json` 自动增加原生状态。

[动作与参考图计划](work/repair-v4/generation-plan.json) 和 [补画要求](work/repair-v4/generation-prompt.md) 已准备好。2026 年 11 月 7 日已在用户授权的 TiMi CC 服务上实际取得 `gpt-image-2` 的 8 张表情图。多帧复合图请求未能取得可解码图像，因此使用逐帧生成，再以固定脸部蒙版合成。待机动画预览与完整宠物包的验收分别记录；项目不会保存或提交密钥。

## 安装器

原来的命令现在可以试装草稿：

```powershell
.\install-pet.ps1
```

脚本默认安装 `draft/spritesheet.webp`，自动备份现有 `pet.json` 和 `spritesheet.webp` 到安装目录的 `backups/` 子目录，并提示完整动画尚未完成。草稿只修复 neutral 默认帧和全透明像素 RGB 残留，已有动作和外观仍是旧稿，不代表最新抠图已变成完整动画。

默认目标为 `$env:USERPROFILE\.codex\pets\ootori-sayumi-pet`，支持 `-Destination` 自定义位置。安装后重启客户端，在宠物选择器中选择 **Ootori Sayumi pet**。

只允许安装验收成品时可运行 `.\install-pet.ps1 -RequireRelease`。当前 `installable=false` 仍保留成品未就绪的状态；该严格模式会拒绝安装并保留现有文件。

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
