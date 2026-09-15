# Ootori Sayumi pet Draft

Based on the primary reference image. Codex v2 atlas: 1536x2288, 192x208 cells, 8x11 rows.

States: idle, happy/jumping, shy/waiting, surprised/failed, thinking/running, greeting/waving, eating (mapped to interaction row pending dedicated source), sleeping (mapped to idle row pending dedicated source).

Files: pet.json, spritesheet-extended.webp, contact-sheet-extended.png, state-map.json, validation-extended.json.

This is a usable draft. Atlas dimensions and v2 metadata are correct; official validation still reports 12 warnings around static rows and transparency thresholds. Dedicated eating and sleeping source art can be added in a later revision.
## 安装到 Codex 客户端

在 VS Code PowerShell 终端运行项目根目录下的 `install-pet.ps1`：

```powershell
.\install-pet.ps1
```

脚本会安装到 `$env:USERPROFILE\.codex\pets\ootori-sayumi-pet`，然后重启 Codex 客户端即可加载。
