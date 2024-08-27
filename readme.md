# MSSQL To [ScyllaDB](https://www.scylladb.com/)/Cassanadra Migrate Using [Kestra](https://kestra.io/) (ETL)

![ApacheCassandra](https://img.shields.io/badge/cassandra-%231287B1.svg?style=for-the-badge&logo=apache-cassandra&logoColor=white)
![MicrosoftSQLServer](https://img.shields.io/badge/Microsoft%20SQL%20Server-CC2927?style=for-the-badge&logo=microsoft%20sql%20server&logoColor=white)

## Transfer all tables into ScyllaDB/Cassandra

<b>etl_script.yml</b><br>
Declare variables based on your configuration

```yaml
variables:
  server_url: jdbc:sqlserver://192.168.21.1:1433;databaseName=test;encrypt=false;
  username: "sa"
  password: "Admin@123"
  schemas: "'dbo'" # 'dbo','person'
  scylla_host: "192.168.10.128"
  scylla_port: 9042
  scylla_user: "cassandra"
  scylla_password: "cassandra"
  keyspace: "test"
```

Create first task & fetch all the tables from your schema.

```yaml
tasks:
  - id: fetch_tables
    type: io.kestra.plugin.jdbc.sqlserver.Query
    url: "{{ vars.server_url }}"
    username: sa
    password: Admin@123
    sql: "SELECT CONCAT(T.TABLE_SCHEMA,'.',T.TABLE_NAME) tbl FROM INFORMATION_SCHEMA.TABLES T WHERE T.TABLE_SCHEMA IN ({{ vars.schemas }})"
    fetch: true
```

Create iterate task which iterate each tables.

```yaml
- id: iterate
  type: io.kestra.core.tasks.flows.EachSequential
  value: "{{ outputs.fetch_tables.rows | jq('.[] | .tbl')}}"
  allowFailure: true
  tasks:
```

Fetch all records from table. <br>
[Note: "store: true" stores the data in [.ion](https://amazon-ion.github.io/ion-docs/) format. ]

```yaml
# FETCH TABLE
- id: fetch_table
  type: io.kestra.plugin.jdbc.sqlserver.Query
  url: "{{ vars.server_url }}"
  username: "{{ vars.username }}"
  password: "{{ vars.password }}"
  sql: "SELECT * FROM {{ taskrun.value }}"
  fetch: true
  store: true
```

Convert [.ion](https://amazon-ion.github.io/ion-docs/) to .csv file.

```yaml
- id: transform
  type: io.kestra.plugin.serdes.csv.CsvWriter
  from: "{{ outputs.fetch_table[taskrun.value].uri }}"
```

Now run python script to insert records (.csv file) into [ScyllaDB](https://www.scylladb.com/)/Cassandra

```yaml
- id: py_insert
  type: io.kestra.plugin.scripts.python.Commands
  runner: PROCESS # DEFAULT IS DOCKER CONTAINER
  allowFailure: true
  namespaceFiles:
    enabled: true
  inputFiles:
    data.csv: "{{ outputs.transform[taskrun.value].uri }}"
  commands:
    - python3 scripts/elt_script.py "{{vars.keyspace}}.{{  taskrun.value | replace({'[A-z0-9]+\.':''},regexp=true)}}"
```

<b>elt_script.py</b><br>
[rscylladb](https://github.com/MeetRathod0/rscylladb) package is require for insert records into [ScyllaDB](https://www.scylladb.com/)/Cassandra

```python
from rscylladb.bulk import bulk_insert
bulk_insert(['192.168.10.129'],9042,username='cassandra',password='cassandra')
```

## CDC using Kestra

#### Enable CDC into source database.<br> e.g. MSSQL

```sql
USE MyDB
GO
EXEC sys.sp_cdc_enable_db
GO
-- Enable CDC for a table specifying filegroup
USE MyDB
GO
EXEC sys.sp_cdc_enable_table
    @source_schema  = N'dbo',
    @source_name    = N'MyTable',
    @role_name      = N'MyRole',
    @filegroup_name = N'MyDB_CT',
    @supports_net_changes = 1
GO
```

<b>cdc_script.yaml</b> <br>
Define configuration variables

```yaml
id: cdc_test
namespace: company.team
variables:
  scylla_host: "192.168.10.129"
  scylla_port: 9042
  scylla_user: "cassandra"
  scylla_password: "cassandra"
  scylla_keyspace: "test"
```

Start capturing from the database.

```yaml
tasks:
  - id: capture
    type: io.kestra.plugin.debezium.sqlserver.Capture
    hostname: 192.168.21.1
    port: "1433"
    username: sa
    password: Admin@123
    database: test
    ignoreDdl: true
    excludedTables: "dbo.ratings"
    metadata: ADD_FIELD
    deleted: DROP
    deletedFieldName: deleted
```

Iterate each captured tables.

```yaml
- id: iterate
  type: io.kestra.core.tasks.flows.EachSequential
  value: "{{ outputs.capture.uris | jq('.[]') }}"
  allowFailure: true
```

Iterate returns each captured records in the form of [.ion](https://amazon-ion.github.io/ion-docs/) file. Convert [.ion](https://amazon-ion.github.io/ion-docs/) to .csv file.

```yaml
tasks:
  - id: csv_transform
    type: io.kestra.plugin.serdes.csv.CsvWriter
    from: "{{ taskrun.value }}"
```

Start python script to insert generate csv file into targeted [ScyllaDB](https://www.scylladb.com/)/Cassandra database.

```yaml
- id: py_load
  type: io.kestra.plugin.scripts.python.Commands
  runner: PROCESS
  allowFailure: true
  namespaceFiles:
    enabled: true
  inputFiles:
    data.csv: "{{ outputs.csv_transform[taskrun.value].uri }}"
  commands:
    - python3 scripts/cdc_test.py
```

## Author

- ### 🙋‍♂️ [Meet Rathod](https://github.com/MeetRathod0)
