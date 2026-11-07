# Ootori Sayumi pet · 稳定待机预览

直接打开 [preview.html](preview.html)，可比较固定身体版、轻微晃动版与实际 192×208 尺寸，切换棋盘、浅色和深色背景。

- 8 张真实生成的表情源图，局部合成为睁眼、眼睑下降、半闭眼、闭眼和重新睁眼的循环；总时长 1,900 ms。
- 身体沿用第一张原始待机插画，保留短腿和交叉站姿。所有帧使用相同画布、缩放和位置。
- 轮廓白边在统一基准上清理一次，再用于所有帧。腿部逐像素一致性相对于这个清理后的基准检查；不声称白边处理前后的透明度完全相同。
- 轻微晃动只在上半身做平滑横移：1024 画布上最多 1.5 px，实际尺寸约 0.28 px；没有身体缩放、旋转或垂直移动，腿部和脚底继续固定。
- 放大发梢仍能看到少量浅边和锯齿；本次是可用待机预览，完整宠物包仍待其余动作、视线和 v2 验收。

文件说明：

- `idle-stable-preview.webp` / `.gif`：固定身体的透明动画。
- `frames-192/`：固定身体版的 8 张实际尺寸 PNG。
- `gentle-sway/idle-gentle-sway.webp`：轻微晃动版大图预览。
- `gentle-sway/idle-gentle-sway-192.webp`、`gentle-sway/frames-192/`：轻微晃动版实际尺寸动画与逐帧 PNG。
- `qa.json`、`gentle-sway/qa.json`：尺寸、帧数、时长、文件指纹、腿部及脚底一致性校验。
- `visual-review.json`：独立视觉复核、实际播放检查、接受的少量边缘问题和当前交付状态。
- `edge-before-after.png`、`edge-cleanup.json`：统一轮廓清理的对比和记录。

本地处理顺序是 `prepare_stable_idle.py` → 逐帧模型编辑 → `assemble_stable_idle.py` → `clean_idle_fringe.py` → `prepare_clean_idle.py` → `assemble_stable_idle.py` → `render_stable_idle_sway.py`。清理参数为 `--depth 12 --white-min 210 --white-spread 35 --trim-white-depth 4`。

Git 记录处理脚本、生成提示词与计划、最终动画、实际尺寸 PNG 和校验结果。原始参考图、派生编辑底图、模型返回的大图和处理大图均保留在原工作区供调试，不随此次提交上传；从 Git 新克隆后可直接看预览，重新处理还需要这些本地输入。生成计划是生成时的快照，最终状态以 `visual-review.json` 和根目录 `PROGRESS.md` 为准。

没有替换现有安装包，也没有将完整宠物标为可安装。
