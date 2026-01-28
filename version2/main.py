from sqlalchemy import create_engine, text
import numpy as np
import os
from dotenv import load_dotenv

# This loads the variables from the .env file into your system's memory
load_dotenv()
# from IPython.core.interactiveshell import InteractiveShell
# InteractiveShell.ast_node_interactivity = "all"
# --- Credentials ---
HOST = os.getenv("DB_HOST")
USER = os.getenv("DB_USERNAME")          # change if your user is different
PASSWORD = os.getenv("DB_PASSWORD")
PORT = 3306
DATABASE = "dfos_sidwal"  # replace with actual DB name


# --- SQLAlchemy connection URL ---
connection_url = f"mysql+pymysql://{USER}:{PASSWORD}@{HOST}:{PORT}/{DATABASE}"
# --- Create Engine ---
print(connection_url)
engine = create_engine(connection_url)


# --- Test Connection ---C:\Users\aakri\OneDrive\Documents\projects\workflow_pattern\graph_traversal_v2.ipynb
try:
    with engine.connect() as conn:
        result = conn.execute(text("SELECT 1"))
        print("Connection OK:", result.scalar())
except Exception as e:
    print("Connection failed:", e)

import pandas as pd
from collections import OrderedDict
_GRAPH_ = []
WFI = 512
SID = 895

def load_cte(name: str, mfi=WFI):
    with open("get_workflow.sql", "r", encoding="utf-8") as f:
        content = f.read()
        sql_cte = content.format(main_form_id=mfi, sid=SID)
    query =  sql_cte + f" SELECT form, connection FROM {name};"
    return pd.read_sql(text(query), engine, dtype=int)

def get_graph():
    def traverse_graph(basedf=None,startdf=None,iteration=0):
        if iteration == 0:
            basedf= load_cte("all_connections")

            startdf=load_cte("root_connections")
            # print( basedf)
            # print( startdf)
        if basedf.empty : #or iteration == 100
            print(f'-----------------------------------------------------------------------------iteration {iteration}')
            sf = startdf
            sf = sf.dropna(subset=[sf.columns[1]])
            sf.drop(columns=[sf.columns[-1],sf.columns[-2]], inplace=True)
            drop_columns = [
                i-1 for i in range(2, len(sf.columns)) if i % 2 == 1
                ]
            sf.drop(columns=[sf.columns[i] for i in drop_columns], inplace=True)
            sf.drop_duplicates(inplace=True)
            # sf["steps"] = sf.count(axis=1)
            sf.reset_index(drop=True, inplace=True)
            sf.columns = ['_'+str(i+1) for i in range(len(sf.columns))]
            sf.sort_values([sf.columns[0], sf.columns[-1]], axis = 0, ascending=True).reset_index()
            sf.index = sf.groupby(sf.columns[0]).cumcount() + 1
            
            if len(sf[sf.columns[-1]].drop_duplicates()) == 1 and pd.isna(sf[sf.columns[-1]].drop_duplicates().iloc[0]):
                sf.drop(sf.columns[-1], axis=1, inplace=True)
                print('last column deleted')
            cross_sections = len(sf.columns)-1
            if _GRAPH_:
                if _GRAPH_[0] == cross_sections:
                    pass
                else:
                    _GRAPH_[0] = cross_sections
            else:
                _GRAPH_.append(cross_sections)
            return sf
        else:
            # print( basedf)
            # print( startdf)
            basedf_merge =  basedf[~basedf['form'].isin([n for n in startdf['form']])]
            print(f'-----------------------------------------------------------------------------iteration {iteration}')


            graphdf = pd.merge( # here the graphdf acquires forms on the basis of connections
                startdf,
                basedf_merge,
                left_on=startdf.columns[-1],
                right_on=basedf_merge.columns[-1],
                how="left",
                suffixes=(f"_foc{iteration}", f"foc{iteration}")
            )

            basedf_merge2 = basedf_merge[~basedf_merge['connection'].isin([n for n in graphdf['connection']])]
            graphdf2 = graphdf[[col for col in graphdf.columns if col!= 'connection']] 
            graphdf3 = pd.merge( 
                graphdf2, 
                basedf_merge2,
                left_on=graphdf2.columns[-1],
                right_on=basedf_merge2.columns[0],
                how="left",
                suffixes=(f"_cof{iteration}", f"cof{iteration}")
            )
            iteration_ = iteration +1
            
            return traverse_graph(basedf=basedf_merge2, startdf=graphdf3, iteration=iteration_)
    gdf = traverse_graph()
    return gdf

def get_fields(workflow:pd.DataFrame=None):
    distinct_nodes = []
    
    for i,r in workflow.iterrows():
        for col in workflow.columns:
            if pd.notna(r[col]) and int(r[col]) not in distinct_nodes:
                distinct_nodes.append(int(r[col]))
    
    distinct_nodes = tuple(distinct_nodes)
    with open('fetch_fields.sql', 'r', encoding='utf-8') as sqlfile:
        querycontent = sqlfile.read()
        query = querycontent.format(form_ids = distinct_nodes)
    fields_data = pd.read_sql(query, con=engine)
    return fields_data 

def get_workflow_query():
    if not _GRAPH_:
        get_graph()
        
    all_connections = f"""
    , next_forms0 AS (
    SELECT form AS _1 FROM all_connections WHERE form IN (SELECT DISTINCT * FROM root_form))
            , connections1 AS (
            SELECT t._1, a.connection
            FROM next_forms0 t LEFT JOIN all_connections a
            ON t._1 = a.form
            )
            , next_forms1 AS (
            SELECT t._1, a.form as _2
            FROM connections1 t LEFT JOIN all_connections a
            ON t.connection = a.connection
            WHERE a.form NOT IN (SELECT _1 FROM next_forms0)
            ORDER BY _2 asc
            )
            """
    chain_cte = [all_connections]
    for i in range(_GRAPH_[0]):
        n = i+1
        if n == 1:
            pass
        else:
            connections = f"""
            , connections{n} AS (
            SELECT {' '.join(['t._'+str(n+1)+',' for n in range(n)])} a.connection
            FROM next_forms{n-1} t LEFT JOIN all_connections a
            ON t._{n} = a.form
            WHERE a.connection NOT IN (SELECT connection FROM connections{n-1})
            )
            """
            next_form = f"""
            , next_forms{n} AS (

            SELECT {' '.join(['t._'+str(n+1)+',' for n in range(n)])} a.form AS _{n+1}
            FROM connections{n} t LEFT JOIN all_connections a
            ON t.connection = a.connection 
            WHERE a.form NOT IN (SELECT _{n} FROM next_forms{n-1})
            ORDER BY _{n+1} asc
            )   
            """
            chain_cte.append(connections)
            chain_cte.append(next_form)
    chain_query = """\n""".join(chain_cte)
    with open("workflow_query_audit_wise.sql", "r", encoding="utf-8") as f:
        content = f.read()
        sql_cte = content.format(wfi=WFI,sid=SID)
    query =  sql_cte + chain_query + f""", chains_indexed AS (
            select next_forms{n}.*, row_number() over(partition by workflow_index) as chain_index, workflow_index from next_forms{n}
            left join root_connections on next_forms{n}._1 = root_connections.form
            )"""
    
    return query

def get_datasets(graph_=None, fields_data_=None):
    if graph_ == None:
        graph_ = get_graph()
    if fields_data_ == None:
        fields_data_ = get_fields(graph_)
    # getting the fields_data as a copy 
    connection_degrees = []

    for i in range(len(graph_.columns)):
        # looping through graph columns by their index values
        connection_degree = graph_[[graph_.columns[i]]].groupby(graph_.columns[i])[graph_.columns[i]].count().reset_index(name='connection_degree')
        # here we get the count of each form in each column to find their connection degrees.
        connection_degree.columns = ['form', 'conn']
        # re-labeling the columns
        connection_degrees.append(connection_degree)

    # 
    connection_degree = pd.concat(connection_degrees, ignore_index=True).drop_duplicates()
    connection_mapping = connection_degree.set_index('form')['conn']
    connections_mapped = graph_.apply(lambda col: col.map(connection_mapping))
    # here we map the columns of the connection degree dataset to the original graph dataset
    fields = fields_data_
    # needless reassignment
    fields_count = fields.groupby('form_id')['field_name'].count().reset_index(name='field_count')
    # getting fields count for each form
    field_mapping = fields_count.set_index('form_id')['field_count']
    # resetting index on column 'field_count'
    fields_mapped = graph_.apply(lambda col: col.map(field_mapping))
    # mapping the fields by using the lambda function

    fields_mapped['signature_fields'] = [tuple(int(r[col]) for col in fields_mapped.columns) for i,r in fields_mapped.iterrows()]
    fields_mapped['signature_conn'] = [tuple(int(r[col]) for col in connections_mapped.columns) for i,r in connections_mapped.iterrows()]
    # print(fields_mapped)
    # here we get the connection signatures and the field signatures together.
    # 

    graph_['signature_fields'] = fields_mapped['signature_fields']
    graph_['signature_conn'] = fields_mapped['signature_conn']
    graph_['signatures'] = [tuple(r[col] for col in ['signature_fields', 'signature_conn', graph_.columns[0]]) for i,r in graph_.iterrows()]
    # print(graph_)
    signatures = graph_['signatures'].drop_duplicates()
    datasets = []
    for sign in signatures:
        dataset = graph_.loc[graph_['signatures'] == sign,:]
        datasets.append(dataset)
        # print(sign)
    for data in range(len(datasets)):
        column_signatures = datasets[data]['signature_conn'].drop_duplicates().iloc[0]
        # print(column_signatures)
        # print(column_signatures)
        col_sign_group = set(column_signatures)
        # print(col_sign_group)
        columns = pd.Series([col for col in graph_.columns[:-3]])
        column_group = pd.Series(column_signatures)

        column_club = pd.DataFrame({'col':columns,
                                    'sign':column_group})
        column_labels = []
        for x in col_sign_group:
            column_ = [col for col in column_club.loc[column_club['sign']==x,'col']]
            # now slice each dataframe. 
            column_labels.append(column_)
        # print(datasets[data])
        # for col_group in column_labels:
        #     print(datasets[data][col_group].drop_duplicates())
        datasets[data] = [datasets[data][col_group].drop_duplicates() for col_group in column_labels]
        # print(data, 'data')
    return datasets

def get_dataset_queries(ds =None):
    ds = get_datasets()
    dataset_queries = [[] for stack in ds]

    stack_queries = []
    for stack_index in range(len(ds)):
        # getting the stacks inside the dataset collections 
        stack = ds[stack_index]
        datasets = []
        for dataset_i in range(len(stack)):
            # getting the datasets in the datasets. 
            datset_index = dataset_i +1
            dataset = stack[dataset_i]
            dataset_columns = dataset.columns
            dataset_indice = tuple(dataset.index)
            for i in range(len(dataset_columns)):
                # getting the union all query for each column in the dataset for the relevant index
                # here is the only true union all we need to deploy.
                
                union = f"""select distinct {dataset_columns[i]} as form, {i+1} as subchain_index, {datset_index} as dataset_index, chain_index from chains_indexed where chain_index in ({','.join([str(n) for n in dataset_indice])}) """
                datasets.append(union)
        stack_queries.append("""union all \n""".join(datasets))
    dataset_queries = """, datasets as (
    select subq.form, subq.chain_index, subq.subchain_index, subq.dataset_index
    , a.fvf_main_form_name
    , a.fvf_main_form_id
    , b.fvf_section_name
    , b.fvf_section_id
    , c.fvf_main_field_name
    , c.fvf_main_field_id
    , c.fvf_main_field_info
    , c.fvf_main_field_info2
    , c.fvf_main_field_info3
    , c.fvf_main_field_info4
    , c.fvf_main_field_info5
    , c.created_at
    from
    (\n""" + """
    union all \n""".join(datasets) + """) subq
    LEFT JOIN form_via_form_main_forms a
    ON subq.form = a.fvf_main_form_id
    LEFT JOIN form_via_form_main_sections b
    ON a.fvf_main_form_id = b.fvf_main_form_id
    LEFT JOIN form_via_form_main_fields c
    ON b.fvf_section_id = c.fvf_section_id
    where a.deleted_at = 0
    and b.deleted_at = 0
    and c.deleted_at = 0
    order by chain_index, subchain_index, dataset_index)
    """
        
    return dataset_queries

#         # dataset_rows = datasets.rpow
def get_audit_query():
    with open('audit_query.sql','w') as f:
        f.write(f"""{get_workflow_query()}\n{get_dataset_queries()} \n SELECT * FROM datasets""")

