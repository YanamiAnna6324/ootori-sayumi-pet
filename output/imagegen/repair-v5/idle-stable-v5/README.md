# Ootori Sayumi pet · 无缝待机

直接打开 [preview.html](preview.html)，可比较固定身体、轻微晃动和 192×208 实际尺寸动画；背景可切换为棋盘、浅色或深色。页面也并排展示相同的首帧与末帧，便于检查循环接缝。

动画使用 8 个逻辑时段，总时长 1,900 ms，表情源帧映射为 `[1, 2, 3, 4, 3, 2, 1, 1]`。因此动画只有 4 种不同表情：眨眼在中段闭合后沿相同表情自然睁开，首帧与末帧完全相同。固定身体版的 WebP 和 GIF 将相邻相同的末帧合并为 7 个编码帧；QA 已逐一核对逻辑时段覆盖、帧时长、首尾可见像素及无限循环标记。

身体沿用原始待机插画，保留短腿与交叉站姿。表情只在脸部蒙版内变化。轻微晃动仅对上半身施加很小的水平位移；腿部与脚底固定。边缘对比见 [v2 轮廓清理记录](../idle-stable-v2/edge-before-after.png)：放大后仍有极窄浅边和轻微锯齿，深色背景下可检查。

文件说明：

- `idle-stable-preview.webp` / `idle-stable-preview.gif`：固定身体动画。
- `gentle-sway/idle-gentle-sway.webp`：轻微晃动的大图动画。
- `gentle-sway/idle-gentle-sway-192.webp`：192×208 实际帧尺寸动画。
- `frames-192/frame-01.png` 与 `frames-192/frame-08.png`：首尾静态帧对照；可见像素一致。
- `idle-stable-contact.png`、`gentle-sway/idle-gentle-sway-contact.png`：8 个逻辑时段的联系表。
- `qa.json`：首尾可见像素、逻辑时间线、编码帧时长、循环标记及固定腿部检查结果；固定身体 WebP/GIF、晃动 WebP 和原生尺寸 WebP 均通过编码时间线检查。

本目录只交付待机预览，不是完整 Codex v2 宠物包。其余标准动作、视线方向、最终图集和安装验收仍未完成；没有替换现有安装素材，也没有将其标记为可发布。
