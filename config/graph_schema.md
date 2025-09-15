# Graph Schema
## Node Details
- `资产负债表` has properties: ['年', '期间', '月', '货币单位']
  - Sample data: {'年': 2024, '货币单位': '', '月': 5, '期间': '2024年5期'}
  - Incoming relations: ['属于资产负债表数据']
  - Relationship patterns:
    - (资产负债表数据)-[属于资产负债表数据]->(资产负债表)

- `资产负债表数据` has properties: ['是否总计', '是否小计', '分类', '年初数', '名称', '期末数']
  - Sample data: {'是否小计': False, '是否总计': False, '名称': '固定资产', '期末数': -2.87999999988824, '年初数': -0.179999999701977, '分类': '非流动资产'}
  - Outgoing relations: ['属于资产负债表数据']
  - Relationship patterns:
    - (资产负债表数据)-[属于资产负债表数据]->(资产负债表)
