# Graph Schema
## Overall Node Types and Relations Types
**Node Types**:

['Voucher', 'Entry', 'Account', 'SalesGroup', 'ExpenseItem', 'CostSubelement', 'AssetCategory', 'Warehouse', 'Customer', 'Project', 'ManualInput', 'Department', 'Supplier', 'OtherParty', 'Org', 'AssetCard', 'Bank', 'BusinessMode', 'Employee', 'InventoryCategory', 'BankAccount', 'UseDepartment', 'CashAccount']

**Relation Types**:

['HAS_ENTRY', 'FOR_CUSTOMER', 'FOR_SUPPLIER', 'IN_DEPARTMENT', 'FOR_EXPENSE_ITEM', 'FOR_PROJECT', 'IN_SALES_GROUP', 'IN_INVENTORY_CATEGORY', 'IN_COST_SUBELEM', 'IN_ASSET_CATEGORY', 'FOR_OTHER_PARTY', 'BY_EMPLOYEE']

## Node Details
- `Voucher` has properties: ['创建时间', '过账人', '期间', '审核日期', '创建人', '来源系统', '来源类型', '记账日期', '修改时间', '凭证摘要', '过账', '审核人', '账簿', '凭证字', '制单人', '状态', 'voucher_id', '凭证号', '来源表单类型', '借方合计', '贷方合计', '复核人', '审核驳回']
- `Entry` has properties: ['原币金额', '币种', '摘要', 'entry_id', '附件数', '序号', '借方', '原币借方', '贷方', '原币贷方', '主表项目金额', '主表项目', '参考消息', '附表项目']
- `Account` has properties: []
- `SalesGroup` has properties: ['name']
- `ExpenseItem` has properties: ['name']
- `CostSubelement` has properties: ['name']
- `AssetCategory` has properties: ['name']
- `Warehouse` has properties: []
- `Customer` has properties: ['name']
- `Project` has properties: ['name']
- `ManualInput` has properties: []
- `Department` has properties: ['name']
- `Supplier` has properties: ['name']
- `OtherParty` has properties: ['name']
- `Org` has properties: []
- `AssetCard` has properties: []
- `Bank` has properties: []
- `BusinessMode` has properties: []
- `Employee` has properties: ['name']
- `InventoryCategory` has properties: ['name']
- `BankAccount` has properties: []
- `UseDepartment` has properties: []
- `CashAccount` has properties: []
