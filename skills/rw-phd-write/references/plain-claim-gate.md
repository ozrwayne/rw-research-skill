# 正文三类禁止

示例里的作者和框架名是编的，不要写进稿子。示例里的研究场景也是编的。

本文件是 rw-phd-write 的写作检查规则。判断看句子在当前段落里起什么作用，不看有没有否定词或某个名词。「硬标记」一节例外：表里列出的标记命中就改。

动作只有五种：

- `KEEP`：保留。
- `DELETE`：删掉。不补同义句。
- `REWRITE`：改成读者能看懂的正面句子。
- `DEFINE_WITH_SOURCE`：这个词在领域文献里有出处。首次出现写出定义和引文。
- `ASK_AUTHOR`：要作者确认称呼、范围或来源。不替作者造一个定义。

## 应保留的边界

下面四类不按本规则删除：

- Methods 里读者复现所必需的边界，写成具体事实。
- Limitations 里的具体事实。
- 结果中的否定，例如某个指标没有变化。
- 领域文献里有出处、并且正文已经给出定义和引文的术语。

能用正面句写清的边界，写成正面句。垫场句不是边界。

## 正向定性与负向约束

### 默认正向定性

同一个意思，优先用正向结构直接陈述它是什么、做了什么、得出什么。能用一个准确的正向词表达 “not + 形容词/动词” 的，用正向词。例：negligible，不用 not large；inaccurate，不用 not accurate。依据是 Strunk & White, *The Elements of Style*, 4th ed., Rule 15 “Put statements in positive form”。此条不引 APA。

### 必须保留、并要写准的负向约束

判断问题：删掉这句，读者会不会高估结论的适用范围或强度？会，就是负向约束。

- 适用边界：写出模型假设、样本范围、方法产出止于何处。要写出具体条件或阈值。例：The diary study does not measure nap length; nap lengths in the simulation come from scenarios.
- 统计推断：fail to reject the null、no evidence against X、置信区间跨过零，保留负向表述。不得改写成正向动词。
- 概念区分：先说不是什么，再说是什么。只在文献中确有人把这两个概念混用时使用，并引出处。没有这种混用时，直接写正向定义。一篇论文里只在核心立论处少量使用。
- 阴性结果与局限：写成具体事实，写出排除了哪个机制、哪个阈值外不成立。放在 Results、Discussion 的局限部分，或 Methods 必需处。

Methods 里的边界陈述就叫边界陈述。不用“防御性写作”指代它。

### 要禁止的免责式负向写作

判断问题：删掉这句，读者对研究的理解有没有变化？没有，就是免责式负向写作。

- 稻草人式否定：“这不是 A，也不是 B，而是 C”。A、B 没有人主张过，或没有出处。动作：`REWRITE` 为直接正向陈述。
- 范围撤回：段落末尾追加“这并不意味着……”“不能一概而论”“当然这不适用于所有情况”，不给出具体条件。动作：`DELETE`。确有边界时，把材料支持的具体条件前置到结论里，例如 “In adults with X, …”。
- 对冲式套话：“仍有争议”“一方面……另一方面……”，没有引出具体相反证据。动作：`DELETE` 或 `REWRITE`。
- 例外：有引文的具体相反证据、不一致的研究结果必须保留。这些是证据。按 rw-phd-write 现有规则，不为流畅删除反例和不确定性。

### 条件前置

条件前置时，不写“当且仅当……必然……”这类比材料更强的断言。用材料支持的条件和原有强度。例：Among students who slept less than 6 hours at baseline, the gain in sleep time was larger。

判断只用上面两个“删掉这句会怎样”的问题。不写章节正负比例或配额。使用负向约束的理由是提高结论精度。

应改：

> The residence-hall sample does not stand for students across the country.

删掉这句，读者对样本是谁的理解没有变化。这是没有具体条件的范围撤回。用材料里已有的样本事实改成正向句，例如：The sample includes first-year students who lived in one residence hall in 2024。材料里没有这些事实时 `ASK_AUTHOR`，不补造。

应保留：

> The diary study does not measure nap length; nap lengths in the simulation come from scenarios.

这是适用边界。删掉前半句，读者会把情景取值当成日记研究的测量值。

应保留：

> The comparison found no evidence against equal means (95% CI −1.2 to 2.0).

这是统计推断。区间跨过零。不得改成 remained stable。

## 造词

定义：作者或助手自己拼出来的名词或名词串。所在领域文献里不是通用术语，读者要猜意思。

判断：先查这个词是不是该领域有出处的术语。日常词组成的句子不算造词。

动作：

- 有出处：首次出现用 `DEFINE_WITH_SOURCE`，写出定义和引文。
- 没出处：用 `REWRITE` 写成谁对什么做什么。不得另补一个定义把自造词留在正文里。
- 不用名词串代替关系。关系写成完整句子。
- 内部讨论用的阶段名、目标名、路径名进入正文前，先向作者确认导师用的称呼，全文只用一套。不确定时 `ASK_AUTHOR`。

应改：

> Each clinic is reported as a sender-channel pair.

读者不知道这个组合指什么。改成：For each clinic, the text states who sends the reminder and which channel they use.

应改：

> Section 3 reviews reminder–attendance evidence.

名词串代替了关系，读者要猜是哪种关系。改成：Section 3 reviews the evidence on whether reminders change clinic attendance.

应保留：

> This chapter uses "example concept" as Author A (2000) defined it: a concept that names a shared feature before any measurement is chosen.

词有出处，首次出现已有定义和引文。

应保留：

> The analysis uses the Example Framework for Service Research (EFSR; Author B et al., 2001).

这是领域里已有的框架名，并给出了引文。

## 承载论证的词

定义：要当模型参数的词，或整段论证建在它上面的词。

判断：动笔前把它拆成四样。有一样说不出，先不用这个词写论断，列进待作者核验清单或 `ASK_AUTHOR`。

1. 操作定义：用什么程序、什么工具测出来。
2. 概念、测量和估计目标分开写：理论上的概念、实际测到的量、模型要用的参数是三样东西。拿测到的量直接当参数时，写出中间的换算和换算依据。
3. 因果链上的位置：写出它前后相邻的环节。两个词落在链上不同位置，就不能互相替换。
4. 单位：写出这个量的单位。单位是几样东西乘起来的，说明这个词还能再拆。

近义词不画等号：同一论证里出现两个意思相近的词（例如 attendance、participation、adherence），写明它们的关系。材料说明不了时 `ASK_AUTHOR`。

动作：`REWRITE` 或 `ASK_AUTHOR`。

应改：

> Library visits are used as the reading-time parameter.

测到的是到馆次数，模型要的是阅读时长。两者之间缺换算。写出换算和来源，或 `ASK_AUTHOR`。

应保留：

> Sleep duration was measured with wrist actigraphy and is reported in minutes per night.

操作定义和单位都清楚。


## 学术搭配与连字符

定义：名词作定语时的连字符、领域固定搭配，以及同一术语在全文里的拼写。

判断：先查这个写法是不是该领域、该国家机构文件里的正式用语。查不到就不猜。

规则：

- 名词作定语时默认不加连字符。例：economic evaluation guidelines。只有不加会产生歧义时才加。同一术语全文用同一种写法。
- 用领域里已有的固定搭配。正式文件名按论文所在国家和机构的用语。例：某机构的正式文件名用 Guidelines，就不改写成 Guidance。来源核不到时用 `ASK_AUTHOR`，不猜文件名。
- 术语本身已经包含的意思，不再加定语造新复合词。longitudinal design 已经包含重复测量。需要说明测了几次时，写成短语 with sleep measured at three time points。不写 repeated-measure longitudinal design。不写 multi-wave longitudinal design。
- 场景或行业名词不直接接 methods、evidence、measurement 一类抽象名词。不写 dormitory sleep methods。写出方法测什么：methods for measuring sleep in student residences。
- 同一术语的拼写和连字符全文一致。例：program 与 programme，health care 与 healthcare。发现不一致时列出，交给作者统一。不在局部改其他章节。

动作：`REWRITE` 或 `ASK_AUTHOR`。

应改：

> The protocol follows sleep-diary guidance.

名词作定语，不加连字符也不会歧义。机构正式文件名还没核对。连字符改掉。文件名用 `ASK_AUTHOR`。

应改：

> The project used a repeated-measure longitudinal design.

longitudinal design 已经包含重复测量。改成：The project used a longitudinal design, with sleep measured at three time points.

应改：

> The study uses dormitory-sleep methods.

场景名词直接接了 methods。读者不知道方法测什么。改成：The study uses methods for measuring sleep in student residences.

应保留：

> The panel issued an evidence-based recommendation.

evidence-based 是放在名词前的标准复合形容词。不是名词作定语硬加的连字符。

应保留：

> The analysis uses the Example Coding Method (Author C et al., 2002).

这是领域专有名，并给出了引文。


## 内部上下文

定义：正文里出现只有作者和助手才懂的过程信息。没参加内部讨论的读者，靠正文和引文看不懂。

范围包括：内部日志或文件、决定编号、会议和导师讨论过程、修订过程说明、助手或模型名称、只在内部笔记里定义过的标签。搜索日志、claim audit 路径、draft-status note 和其他内部交接说明属于这一范围。

判断：一个没参加过内部讨论的读者，能不能靠这一句和引文看懂。看不懂就删或改写。

动作：过程信息用 `DELETE`。给导师的说明和待定事项放在单独说明里，不放正文。读者能从正文和引文看懂的句子用 `KEEP`。

应改：

> As recorded in decision D-14, the review log retains the screening spreadsheet.

导师和审稿人看不到这份日志，也没有决定编号。删掉这句。筛选结果若需要报告，改写成正文或附表里已经给出的数字。

应改：

> The drafting note says the assistant renamed this step "rest score" before the meeting.

这是修订过程说明，并写出了助手。删掉过程，只留读者需要的定义：The rest score is the number of nights per week a student reports sleeping at least seven hours.

应保留：

> Screening decisions and the reasons for exclusion are listed in Supplementary Table 2.

读者能在附录里找到这张表。这不是内部文件名。

应保留：

> The interview guide asked participants who sends appointment reminders in their clinic.

这是方法事实，读者不需要内部笔记就能看懂。

## 硬标记

本节的标记命中就改。例外只按表里写的，表外的词不按本节处理。本节不含 not、but、rather than：否定句照「正向定性与负向约束」一节判断，统计推断、适用边界、有出处的概念区分、阴性结果里的否定句照旧保留。

适用范围：英文正文、中文正文，以及写给作者看的中文说明（状态表、修改说明、检查记录）。生成和复查都扫。作者稿里批准范围外的命中，列进交付检查记录，标为必须改，等作者批准后再改。

| 标记 | 怎么改 | 例外 |
|---|---|---|
| 句中破折号：—，两侧带空格的 –，中文 —— | 改成逗号、括号或冒号，或拆成两句 | 数值范围和页码范围里的连接号（2019–2021，pp. 10–12）；引文括号里的连接号；复合形容词里的连字符（evidence-based）；负号（−1.2） |
| 问号，后面没有紧跟证据给出的回答 | 改成陈述句，直接写要说明的内容 | 研究问题本身（Research question 1: …?）；直接引语；问卷或访谈题目原文 |
| may、might、could、possibly、perhaps，用来软化论断 | 有证据就直接写结论并给引文；只支持关联就写 is associated with；没排除的因素写成具体局限句；没有证据就删 | 表示许可或规定（Participants may withdraw at any time.）；表示能力或条件（Two students could not be contacted.）；直接引语；来源原文这样写且按原文引述 |
| suggest、suggests、suggested，用来软化论断 | 同上一行 | 直接引语；来源原文这样写且按原文引述 |
| 数字前主动加的 approximately、around、about | 删掉，回到来源原文的数字和措辞 | 来源原文就这样写 |
| serves as、stands as、marks、represents、boasts、features、offers，能直说 is 或 are 时 | 改成 is 或 are | 这些词表示实际动作时（The nurse marks each form.） |
| linked to | 改成 associated with；有因果设计时写出具体关系 | 数据或记录的连接（Records were linked to the enrolment register.） |
| via | 改成 through 或 by means of | 直接引语 |
| 句首 Beyond 用作过渡 | 改成 In addition to，或直接写下一点 | Beyond 表示空间或数量超出（Beyond 5 km, …） |
| yield、yields、yielded 用作结果动词 | 改成 produce、provide 或 generate；没有结果时写 did not produce | 化学产率、农业产量 |
| 逗号后接非地点的 where 从句 | 改成独立句、括号或介词短语 | where 指地点或场合（the clinic where the pilot ran） |
| 压缩表达：用连接号把两个名词压成一种关系（reminder–attendance）；mutual reinforcement、bidirectional relationship、complex interplay 这类抽象速记 | 展开成谁对谁做了什么 | 文献里有出处、正文已给定义和引文的术语 |
| 中文里的“不是……而是……”，正文和说明都算 | 直接写是什么 | 无 |
| 中文里的“而非”，正文和说明都算 | 直接写是什么 | 无 |

硬标记由执行者逐项扫描，结果记进交付检查记录：位置、原文、按哪一行改、改后文字。它不进交叉检验的类别。

应改：

> Students in the late-start group slept longer — about 40 minutes more per night.

句中破折号，加上来源没有的 about。来源写 38.6 分钟时改成：Students in the late-start group slept 38.6 minutes more per night.

应改：

> Why did attendance rise after the reminder change? Section 4 describes the clinic schedule.

问号后面没有给出回答。改成陈述句：Section 4 describes how the clinic schedule changed when attendance rose.

应改：

> Shorter waiting times may improve attendance.

may 软化了论断。有因果证据时直接写结论并给引文。只有关联证据时写成：Shorter waiting times were associated with higher attendance (Author E, 2004). 没有证据时删掉。

应保留：

> Attendance rose from 61% to 74% (95% CI 2–24) in 2019–2021.

区间和年份范围里的连接号不算句中破折号。

应保留：

> Research question 1: Do text reminders change missed appointments in student clinics?

这是研究问题本身，问号保留。

应保留：

> Participants may withdraw at any time without giving a reason.

may 在这里表示许可，照旧保留。

## 与对照检查的分工

`references/abstract-contrast-gate.md` 仍然规定：出现 not 或 but 不单独构成问题。本文件不推翻那一条。否定句起免责作用、没有陈述适用边界、统计推断、有出处的概念区分或阴性结果时，本文件判需要修改。破折号、问号和套话按本文件「硬标记」一节处理。

## 交叉检验

生成时遵守上面三条。交付前还要交叉检验。

1. 至少两个不同模型各自独立检查同一段文字，互相看不到对方结果。同一模型查两遍不算交叉。
2. 每个模型按本文件逐条输出：位置、原文、类别（防御、造词、内部上下文、搭配）、理由、建议动作。
3. 合并时不投票。两边一致的进入修改建议。只有一边标出的，或建议动作不同的，单列给作者，附上双方理由。任一模型标出的都列出。
4. 改完后再交叉检验一次。确认没有新增同类问题，主张范围也没有被改大或改小。
5. 使用包内交叉检验脚本。审查上下文包含本文件。在任务环境里由另一个模型执行。作者当次指定了可用模型时，只用指定的模型。
6. 只有一个模型可用时，结果标为“未交叉检验”。不写成已经完成交叉检验。
