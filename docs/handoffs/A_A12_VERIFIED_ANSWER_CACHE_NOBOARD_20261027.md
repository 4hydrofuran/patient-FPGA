# A12 核验模型答案复用无板交接

用户允许已核验模型答案复用且保留来源。执行方案C0～C5已完成实现与实际PC验证；入口 `release/a12_verified_answer_cache_20261027/START_HERE.md`。

当前三病例11事实、每问至多两事实，共198键；均由实际Qwen CPU贪心生成并经原checker/EOS接受，没有teacher forcing或模板填充。
目录702482字节，SHA `62cc916342da8d91bb0711db5d6b8095444270332066bc2420c134571a709a13`。
每问仍原路由、事实复核、新回执与评分；MODEL_CACHE明确本轮无模型调用、actual_backend=null，原CPU来源独立保留。
未命中原34-token链，BOARD仍FPGA_REQUIRED；原24输出、1024上下文、10584预留不变。

真实同机HTTP/SSE+Edge25对完整核验答案绘制：中位875.0→42.3ms，逐题减少中位835.8ms，缓存25/25低于1秒。
39网页测试、15浏览器回归、198来源复核、1次真实CPU未命中、7策略零模型、同场20分冻结与10场归档通过。
新部署副本另经真实浏览器25题、启动前目录/依赖准备及正常CPU worker退出0验证。

最初UI配置“极高”；UI控制几何/激活失败后，调用本聊天配置接口设置Sol/High，UI核实“高”。各阶段推荐均High，
不追认先前或单次执行的实际参数。失败与修复存evidence/SETTINGS和FAILURES；没有大规模安全审查、训练、HLS/公共ABI改动或推送。

旧v2包、历史PASS与失败保持。新BOARD尚未执行；板端可见时延、PL计数/CMA/功耗、正常恢复和独立释放均NOT_TESTED/null。
下次另获授权后只需少量缓存可见问题、一例实际PL未命中和原Owner正常释放；不得把CPU缓存数字当成板端成绩。
