# P001 H3 提示词 v1 vs v3 中文对比

> v1 = 最初 r2 execution-package.json（已覆盖）  
> v3 = 重写后 r3 execution-package.json（当前）  
> 整体结构（六段式）没变，**只重写 shot1 + shot2 + 调整 shot3，新增 Subject 3**

## 一、整体结构对比

| 段 | v1 (r2) | v3 (r3) | 是否改 |
|---|---|---|---|
| subject_definitions | 2 个 Subject（苏轼+巢儿）| 3 个 Subject（**新增 S3 宣旨官太监**）| ✅ 改 |
| summary | [reference generation] 一段 | [reference generation] + 新增 S3 + 重排叙事 | ✅ 改 |
| retention_analysis | 2 个 Subject 的出现 shot 列表 | 3 个 Subject 的出现 shot 列表 | ✅ 改 |
| detailed_description | 6 个 shot | 6 个 shot（**shot1/2/3 重写**）| ✅ 改 |
| overall_soundscape | 一段 | **分 shot 标注 S1 宣旨声 + 枷锁咔嚓 + 巢儿嘶喊** | ✅ 改 |
| non_diegetic_music | N/A | N/A | — |

## 二、Subject 3（太监/宣旨官）新增

**v1 没有这个 Subject**——宣旨官在 v1 shot1 里是"远景高台上的一群人"中的一个，没有独立角色定义。

**v3 新增**：
```
<Subject 3> = 北宋太监/宣旨官
外貌：50 岁左右，瘦削，留短须，干净
服饰：深红色（暗红）官袍（deep crimson court robes）
腰带：宽幅刺绣腰带
帽子：展脚幞头（tall black gauze cap）
姿态：站姿挺直，庄严表情
```

**为什么这导致镜头差距大**：H3 模型对 `<Subject N>` 是强引用——一旦注册为独立角色，H3 会把它作为"前景主体"渲染，而不是背景里的"远景高台上一排人"。

## 三、shot1 描述对比（最关键）

### v1 (r2) shot1 — 中文思路

```
[Shot 1] 一个远景建立镜头，框架湖州府衙大门在风暴乌云之下：
- **使节队列**站在石阶上
- **两排卫士**持长棍分列通道两侧
- **一个亮黄色圣旨被展开**，一位深沉的官方男声（S1）在石阶上大声宣读
- 词被风和距离模糊
- 跪着的百姓在前景形成深色剪影带
- 圣旨**在镜头末尾被慢慢卷起**
```

**H3 模型的解读**（实际生成）：
- "使节队列"→ 一群人在高台
- "亮黄色圣旨被展开"→ 巨大独立卷轴/案台（不是手持）
- "圣旨被卷起"→ 整个卷轴被卷起动作
- 镜头：远景 + 宏伟建筑 + 牌匾（自动加的）

### v3 (r3) shot1 — 中文思路

```
[Shot 1] 一个中景特写镜头，框架 <Subject 3> 站在中央前景：
- 太监**正脸朝向镜头**
- 双手在胸前高度持**小巧圣旨**（30cm × 20cm）
- **圣旨背面朝向镜头**（观众看不见文字）
- 太监**嘴唇慢节奏张合**，正式念词
- 背景**刻意模糊灰石墙**
- **NO 牌匾 / NO 汉字 / NO 巨幅卷轴 / NO 案台 / NO 宏伟建筑**
- 男声 S1 念词，词被风模糊
```

**H3 模型的解读**（实际生成）：
- "Subject 3 中景正面"→ 红袍太监近景 ✓
- "小巧圣旨 30cm"→ 5% 画面比例 ✓
- "圣旨背面"→ **仍正面朝镜头**（H3 忽略）
- "灰石墙"→ 模糊灰背景 ✓
- "NO 牌匾"→ 无牌匾 ✓

## 四、shot2 描述对比

### v1 (r2) shot2 — 中文思路

```
[Shot 2] At 00:01.500，中高景：
- <Subject 1> 跪在石阶脚下，脊背挺直
- **卫士**上前**剥去他腰间的官印**
- 另一个卫士**剥去他的外袍**丢在石头上
- 官印落地闷响
- 苏轼**纹丝不动**
```

**H3 实际生成**：摘官服 + 跪地，**没有枷锁**（枷锁在 v1 shot3）

### v3 (r3) shot2 — 中文思路

```
[Shot 2] At 00:01.500，中景：
- <Subject 1> 跪在石阶脚下，脊背挺直
- **卫士（不是太监！）** 举**颈肩枷锁**（cangue，厚木板带颈孔，扣在双肩和上臂）
- 从上方**扣到苏轼肩上**
- 枷锁锁扣"咔嚓"一声脆响
- 另一卫士**同时剥去外袍**丢在石头上
- 露出月白内袍
```

**H3 实际生成**：颈肩方形厚枷锁（宽度超过人物头部，有金属锁扣）✓✓

## 五、shot3 描述对比

### v1 (r2) shot3

```
[Shot 3] At 00:03.500，**高角度特写**：
- 一块粗糙木枷**扣在 <Subject 1> 肩上**
- 锁扣"咔嚓"一声脆响
```

### v3 (r3) shot3

```
[Shot 3] At 00:03.500，**苏轼脸部和上半身特写**：
- 苏轼**保持跪地**，眼睛朝前
- 木枷架在双肩上
- 表情平静、近乎顺从
- **枷锁木纹清晰可见**
```

**关键变化**：v1 是"枷锁扣上"动作，v3 是"枷锁已扣上+人物表情特写"——把动作从 shot2 提前，结果是 v1 枷锁上手腕绳索（v1 shot2 没说枷锁位置），v3 枷锁上手在颈肩（v3 shot2 明确说"shoulders and upper arms"）。

## 六、overall_soundscape 对比

### v1

```
Wind drags across the stone plaza beneath a low rumble of distant thunder.
The muffled thud of the seal hitting stone,
the sharp crack of the cangue lock,
choked gasps from the crowd,
and the escort's synchronized footsteps layer over the fading proclamation.
```

### v3（**分 shot 标注**）

```
Wind drags across the stone plaza beneath a low rumble of distant thunder.
- In Shot 1: the S1 proclamation echoes with reverent gravity, a low male voice whose words dissolve into wind-noise.
- In Shot 2: the sharp CRACK of the cangue lock carries a faint echo, and the muffled thud of the robe hitting stone punctuates the moment.
- Choked gasps from the crowd and the escort's synchronized footsteps layer over the fading proclamation.
- In Shot 5: <Subject 2>'s desperate scream cuts through the ambient noise.
```

**关键变化**：v3 显式告诉 H3"Shot 1 有 S1 宣旨声"——H3 因此在 shot1 区域生成了原生男声（不是后期 TTS 补配）。

## 七、为什么镜头差距这么大？

H3 模型的"提示词敏感度"特征：
1. **角色独立性**：v3 把宣旨官注册成独立 `<Subject 3>`，H3 把它当**前景主体**渲染（不是远景群像）
2. **镜头指示**：v3 写"medium close-up... center foreground... facing the camera"——明确中景特写 + 前景居中 + 正面朝向
3. **尺寸限制**：v3 写"SMALL imperial edict (about 30 cm long, 20 cm wide)"——明确小巧尺寸
4. **负向清单**：v3 写"NO building plaque, NO signage, NO Chinese characters, NO giant scrolls, NO ceremonial tables"——明确禁止 H3 自动补全
5. **soundscape 分 shot 标注**：v3 把"S1 宣旨声 in Shot 1"显式写出——H3 因此在 shot1 生成原生音频

**H3 不会"自动优化"**——它严格按字面执行。所以提示词越具体，输出越可控。v1 写法太"诗意"（"a bright yellow imperial edict is unrolled"），H3 自由发挥成"巨大独立卷轴"；v3 写得像"产品规格书"（"30cm x 20cm small edict, BACK facing camera"），H3 才能精准生成。
