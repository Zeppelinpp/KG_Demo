# Graph Schema
## Overall Node Types and Relations Types
**Node Types**:

['人员', '仓库', '供应商', '客户', '银行账户', '业务单元', '费用', '银行类别', '凭证', '余额', '科目']

**Relation Types**:

['使用科目', '对应科目', '由...制单', '由...审核', '属于客户', '涉及银行', '涉及供应商', '涉及费用', '涉及仓库', '涉及人员', '对应客户']

## Node Details
- `人员` (460 nodes) has properties: ['用户名', '类型', '人员id', '工号', '人员使用状态', '姓名', '序号', '性别', '用户禁用', '手机号码', '负责人', '部门', '职位', '兼职', '直接上级']
- `仓库` (35 nodes) has properties: ['控制策略', '使用状态', '序号', '名称', '可发量控制', '创建组织', '仓库id', '编码', '仓库负责人']
- `供应商` (845 nodes) has properties: ['医药供应商属性', '原创建组织', '供应商状态', '使用状态', '供应商id', '编码', '名称', '序号', '控制策略', '创建组织', '伙伴类型', '可VMI', '统一社会信用代码', '简称', '内部业务单元']
- `客户` (1003 nodes) has properties: ['客户id', '业务职能', '控制策略', '客户名称', '客户编码', '可用状态', '伙伴类型', '序号', '医药客户属性', '创建组织']
- `银行账户` (16 nodes) has properties: ['银行账户id', '账户状态', '使用状态', '控制策略', '账户性质', '申请公司', '序号', '最后更新时间', '账户类型', '最后更新人', '账户简称', '银行类别', '开户公司', '银行账号', '金融机构类别', '币别范围', '开户行']
- `业务单元` (25 nodes) has properties: ['编码', '名称', '使用状态', '形态', '资产职能', '核算组织', '采购职能', '库存职能', '结算职能', '销售职能', '收付职能', '质检职能', '生产职能', '研发职能', '业务单元id', '核算组织类型', '税务职能', '资金职能']
- `费用` (88 nodes) has properties: ['是否叶子', '叶子', '名称', '关联单据', '编码', '使用状态', '控制策略', '费用id', '级次', '级次.1', '创建组织', '序号', '上级', '上级.编码']
- `银行类别` (4059 nodes) has properties: ['最后更新时间', '使用状态', '序号', '名称', '最后更新人', '编码', '银行类别id', '行别代码', '简码']
- `凭证` (100 nodes) has properties: ['科目名称', '修改人', '科目全名', '原币借方', '科目编码', '币种', '原币金额', '摘要', '借方', '凭证id', '附件数', '序号', '期间', '创建时间', '审核日期', '过账人', '来源系统', '借方合计', '修改时间', '创建人', '来源类型', '过账', '凭证摘要', '凭证字', '审核人', '记账日期', '状态', '凭证号', '账簿', '贷方合计', '制单人', '贷方', '原币贷方', '附表项目', '来源表单类型', '审核驳回', '核算维度.客户.编码', '核算维度.销售组.名称', '核算维度.客户.名称', '核算维度.供应商.名称', '复核人', '核算维度.部门.名称', '供应商编码', '费用编码', '仓库编码', '人员编码', '银行账号', '客户编码']
- `余额` (355 nodes) has properties: ['期间', '科目名称', '本期发生额.贷方金额', 'fbalance_id', '科目编码', '本年累计.借方金额', '期末余额.贷方金额', '本年累计.贷方金额', '时间', '序号', '基础资料属性', '本期发生额.借方金额', '期末余额.借方金额', '年初余额.贷方金额', '期初余额.贷方金额', '期初余额.借方金额']
- `科目` (74 nodes) has properties: ['编码', '名称']

## Relationship Details
- `使用科目` (190 relationships) has properties: []
  - Common patterns:
    - ['凭证'] -> ['科目'] (frequency: 95)
- `对应科目` (686 relationships) has properties: []
  - Common patterns:
    - ['余额'] -> ['科目'] (frequency: 343)
- `由...制单` (200 relationships) has properties: []
  - Common patterns:
    - ['凭证'] -> ['人员'] (frequency: 100)
- `由...审核` (200 relationships) has properties: []
  - Common patterns:
    - ['凭证'] -> ['人员'] (frequency: 100)
- `属于客户` (190 relationships) has properties: []
  - Common patterns:
    - ['凭证'] -> ['客户'] (frequency: 95)
- `涉及银行` (26 relationships) has properties: []
  - Common patterns:
    - ['凭证'] -> ['银行账户'] (frequency: 13)
- `涉及供应商` (190 relationships) has properties: []
  - Common patterns:
    - ['凭证'] -> ['供应商'] (frequency: 95)
- `涉及费用` (170 relationships) has properties: []
  - Common patterns:
    - ['凭证'] -> ['费用'] (frequency: 85)
- `涉及仓库` (64 relationships) has properties: []
  - Common patterns:
    - ['凭证'] -> ['仓库'] (frequency: 32)
- `涉及人员` (38 relationships) has properties: []
  - Common patterns:
    - ['凭证'] -> ['人员'] (frequency: 19)
- `对应客户` (720 relationships) has properties: []
  - Common patterns:
    - ['余额'] -> ['客户'] (frequency: 360)
