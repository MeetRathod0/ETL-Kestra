from rscylladb.cdc import cdc_insert
cdc_insert(['192.168.10.129'],9042,'test',username='cassandra',password='cassandra') 
                                    # keyspace