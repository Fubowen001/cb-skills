# 人脸、手部与文字精修

完整微观场景包含主体、环境和原图可辨认的细节。整景高斯重建只是基础，不是严格细节验收的终点。

## 检查与保护
逐人编号，记录表情、眼镜、五官、手势、遮挡及可读文字，保存原图哈希。源图、参考图、基准模型的坐标系不能混用。另建精修版本，已认可资产不得改写。只保守补全不可见厚度和背面；单图不能确定真实隐藏形状。

## 工具的适用边界

scripts/refine_surfaces.py 提供的是源图约束的局部曲面与手部表面，不等于完整头部拓扑、真实隐藏面或角色网格精雕。动画风格使用统一的风格纹理和造型，不贴回写实照片脸。若完整头部单独重建质量较好，保留其三维体积，再按 [装配与验收](production-and-review.md) 校准解剖锚点、比例和颈根；不能只因正面清晰就接受漂浮的脸或头身接合。

## 本机工具
精修运行库位于 runtime/detail/packages 和 runtime/detail/models。scripts/install_detail_runtime.py 从已准备的官方模型和包安装到稳定缓存。运行库、私照和个人关键点不打进技能代码包。

1. scripts/extract_landmarks.py IMAGE --rois ROI.json --out landmarks.json
   ROI 含 faces/hands 数组，每项为 [中心x,中心y,边长]，按身份排序。局部检测可补整图遗漏。missing_* 必须处理。检测错误可用 manual_faces/manual_hands，保存 reviewed、reason、pixel_landmarks；手21点，面468或478点。必须实际对照眼口和指节，数量正确不等于位置正确。
2. scripts/refine_surfaces.py SPEC.json [--job-root DIR]
   SPEC 含 asset、output（新目录）、source、source_landmarks、reference_landmarks、target_landmarks、camera、target_face_centers、style。路径相对任务根。camera 含 width,height,fov,camera（三维眼点），来自基准资产实际预览视角。按原图身份匹配目标头部，不得错配；hand_targets 可设 center、scale。face_depth_scale、hand_depth_scale 控制保守厚度，用侧面排查鼓包和纸片。非 source 风格须提供核对过的 style_texture，不能漂移身份。cleanup_regions 只清有证据的重建残片，必须写 reason。
3. Blender --background --python scripts/create_text_geometry.py -- --spec TEXT.json --out glyphs.json
   TEXT.json 为数组，每项含 id,text,font（本机字体路径）,bbox（校准视角像素）,color。可选 metallic、thin、remove_mode、gaussian_budget。缺字体直接失败；仍须目视排除缺字方框。逐字核对大小写、换行、标点。原图不可读的文字不能猜写，应保留原图纹理并列未知项。
4. scripts/apply_text_geometry.py NEW_ASSET --geometry glyphs.json --camera CAMERA.json --source IMAGE
   在未批准的新版本加入倒角挤出字形与面积加权高斯。印刷小字采用薄浮雕，字球/立牌采用实体字形；不能用屏幕覆盖文字冒充模型修复。拒绝重复添加相同ID。
5. scripts/make_preview.py 与 scripts/export_blender.py 按文件说明运行。Blender 保留完整高斯参数、明确标注的抽样预览、原图UV面部、闭合手部和实体字形。高斯不等于全场景多边形拓扑。
6. scripts/audit_details.py ASSET --requirements requirements.json
   requirements 含 faces 人数、hands 可见手数、texts 精确字符串数组。输出结构检查结果，视觉结论另行填写。

## 验收
逐张脸和逐只手对照原图，查看正面与左右斜视：身份、表情、手指姿势、遮挡、拼接和真实厚度。文字在模型内近看可读，旋转有厚度，不重复、不悬浮、不被旧乱码遮盖，保持原图位置和风格。远观检查精修没有破坏完整场景。

保存截图、视角、源图哈希、检查结论和未通过项。自动检查通过、文件成功导出、正面投影清晰均不等于严格全角度还原。可修复问题继续修复；不能用“完成”或“最终品质”掩盖未通过项。

手部颜色阈值可能切断暗色指节。可用 hand_mask_mode=skeleton 保持骨架连通，或 hand_silhouettes 按手序号提供 reviewed、reason、原图像素 polygon，逐边核对轮廓。hand_cleanup_margin 和 hand_cleanup_mode=all 只在近看证实旧手残影后使用，必须填写 hand_cleanup_reason，并检查腕部未被清理悬空。

用 Blender --background --python scripts/audit_blender_details.py -- ASSET 对实际保存的 .blend 再检查：手部边界闭合、文字三个方向尺寸非零、源图纹理已打包。该检查不会批准视觉质量。
