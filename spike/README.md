# spike/ —— 丢弃型验证脚本，**不要当实现参考**

这些脚本只为了回答可行性问题："Windows 能不能靠一个虚拟声卡拿到一个可用的麦克风，
并且把手机推来的 16k/mono/PCM16 流**无损**送到任意录音程序？"

结论已经冻结在仓库根的 `PLAN.md` §3 和 `docs/` 里的验收数字。**正式实现是仓库根的
`pc_receiver.py` + `app/`，不是这里。** 这里的代码有大量为了快而做的取舍（写死设备索引、
没有抖动缓冲、没有重连管理），照着改成生产代码会踩坑。

| 文件 | 当初回答的问题 | 现在的价值 |
|---|---|---|
| `probe_pc.py` | 端到端编排：UDP 冒充手机 → CABLE Input → CABLE Output 采集 → 量化延迟 | 延迟测法的参考（换 WDM-KS/`latency=low` 从 330ms 降到 143.9ms 就是这么测出来的） |
| `receiver.py` | 最小接收端（UDP 版） | 已被 `pc_receiver.py`（TCP + adb reverse + 弹性缓冲）取代 |
| `fakephone.py` | 按 20ms/包节奏把 WAV 冒充成手机推流 | 想在**没有平板**的情况下复测 Windows 段时还能用 |
| `fidelity.py` | 用冲激定位对齐点，再算重叠段皮尔逊 r + 分频带能量比 | **这个方法本身有价值**：比较区间必须卡在实际发送的秒数内，否则拿后半段静音比语音会得出 r=0.03 的假阴性（踩过） |
| `captured_mic.wav` | 经虚拟麦录下的 JFK 音频（ASR 逐字认对的那段） | 证据文件，不入库（见 `/.gitignore`） |

`spike/captured_mic.wav` 没提交进 git —— 音频证据太大且 `docs/` 里的数字已经足够。
