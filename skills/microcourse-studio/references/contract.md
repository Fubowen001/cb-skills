# 项目合同与版本控制

项目文件夹独立于 Skill。复用 assets/project.example.json，确认输入后再运行。选题是必填信息；已有风格、主题、字体必须复用。学科、学段、时长、目标、设备、画幅、用途不全时先提出明确假设并随内容包送审。示例的三分钟是示例；《元日》使用7—8分钟、三年级、16:9 1080p60。批准前不能把估计当用户要求。竞赛文件、版本、素材授权和评分细则只有用户提供或能核实时才引用。

**机器字段**　version=1。brief 中 subject、audience、topic、theme、style、objective 为非空文本；fonts 含 title/body/caption，可扩展 pinyin/math。fps、width、height、duration_frames 均为正整数。时间统一用整数帧，起点含、终点不含。shots 数组按实际展示时间排列，例 {"id":"S01","start":0,"end":180,"route":"local"}。route 取 still/local/external。混合镜拆成独立展示区间，叠化重合只归属一个主镜；待付费占位保留 external 表示规划占比，结算时用真实成片更新并标注计划值或实际值。

**交付索引**　bundles 的每一项是“产物角色 → 项目内非空文件相对路径”的字典。content 要 outline/script/transcript；board 要 frames/shot_script/transcript/design/tech_audio_plan；prototype 要 browser/timeline；final 要 browser/video/transcript/qa；editor 要 draft/sources/import_qa。加入所有影响审阅的输入、单张分镜图、声音参考、共享样式、网页资源和实际媒体为额外键，或交含全套依赖的版本化压缩包。只有索引而没有被引用的文件不能冻结完整版本。审阅交付前实际打开文件，空壳或链接占位不得列作成品。

**可读制作数据**　每条 cue 包含 cue_id、shot_id、说话者、显示原文、发音文本、起止帧、情绪、重音、口型方式、字幕切分、音源。逐镜制作表包含 start/end、cue_ids、目标与动作、资产ID、首尾姿态、背景与固定锚点、构图、入出转场、教具/实验变量、交互及反馈、音乐/音效落点、渲染路线、提示词与验收点。每次导出互查 cue 所引镜号存在、音频时长匹配、字幕与读音版本一致、题目答案可复算、图片真实可读。修改意见接收 {"version":"v3","notes":{"S02":"具体意见"}}；未知镜号、过期版本、重复冲突记录单列请核对，不自动覆写新版。

**运行方法**　在技能目录执行 python scripts/check.py /项目路径/manifest.json --action content。获得产物后用 --fingerprint content 打印本次材料指纹；把指纹随审阅件交用户。得到用户明确回复后，将 approvals.content 写为 {"fingerprint":"返回值","user_message":"原审批消息或可溯源引用"}。board、final 同法。脚本不会代人批准。先审 content，再用 --action storyboard；审 board，再用 --action prototype；初版可播放后 --action refine。脚本指纹逐阶段链入上游文件和时间轴。需要改早期交付件时回到受影响关口重算并送审，不让旧批准给新版本放行。旧的可播放工程另存版本。open_issues 记录尚未解决的意见；用户接受的遗留项移入单独记录并写明依据，不能为过关直接清空。

**付费批次**　batch 示例：
```json
{"status":"prepared","plan":{"batch_id":"b01","operation":"sample","model":"服务实际模型ID","resolution":"最低可用档","items":[{"shot":"S02","seconds":4,"count":1}],"quote_max":12},"approval":{"fingerprint":"待生成","user_message":"","ceiling":12}}
```
金额仅是语法示例。--batch-fingerprint 打印待审报价指纹；向用户列全内容后记录批准，再执行 --action paid。无预报价用 null，批准记录必须含 accept_actual=true，默认只准备一条一次；额外批量须重新议定。请求ID、目标账号/空间、参考文件摘要、服务返回参数、计费单位等放入 plan 一并冻结。执行者先独占项目写锁、重新校验、原子持久化 status=submitting 及唯一提交ID，然后才发请求，其他执行者不得再投递。accepted/unknown 查原ID，succeeded 保存结果和账本，failed 标记服务是否受理并回到审阅。脚本仅做离线检查，不承担锁、交易、服务端授权或身份认证。定稿审批后 --action import；草稿真实打开且证据齐全后 --action deliver。
