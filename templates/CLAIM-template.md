# CLAIM.md — <一句话标题>

```yaml
claim:
  sentence: "<一句可证伪的话：在条件 Z 下，f(X;Z) 具有性质 P，阈值 T。只写现象与阈值，不写任何方法名（Sparking 第一层）>"
  metric: <metric name>            # 记录里的 metric 字段必须与之相同
  held_out: "<从不进入任何训练条件的测试类别>"
  keep_gain: <数>                   # ≥ 该 cell 的 MDE（项目：sd 0.564 → MDE 1.71）
  keep_networks: <数>
  clean_cost_max: <数>
  seeds_for_keep: 3
  kill_floor: <数>
  kill_frac_of_best: 0.5
  kill_gpu_h_cap: <数>
  stop_hours_no_improve: 24
  stop_search_gpu_h: 24
  networks: [<主网络>, <支持阶梯网络>, ...]
  chains:
    alpha: {gpu: 0, seed_method: "<incumbent：论文需要的现成对照方法，不是候选>"}
    beta:  {gpu: 1, mode: baseline, seed_method: "<对照链要原样实现的基线>"}
  a_terms: [<领域词，用于先例检索>]
  held_out_terms: [<held-out 类别的词，规格里禁止出现>]
```

## 唯一的 claim
## 为什么是这一条（insight）
## 文献核对（一次，≤8 篇）
## 证据表（填满即完成）
## 规则（脚本执行）
## 对照方法（incumbent：每条链一个现成基线；候选由 mechanism 阶段产生，这里不写候选）
## AVOID
