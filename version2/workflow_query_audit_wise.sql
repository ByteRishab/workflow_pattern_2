SET @submission_id = {sid};
SET @wfi = {wfi};
WITH module as (
  SELECT 
    distinct t1.module_id 
  FROM 
    form_via_form_main_forms t1 
  WHERE 
    t1.fvf_main_form_id IN (SELECT distinct fvf_main_form_id FROM form_via_form_main_forms WHERE universal_tag_id = @wfi)
),
 submissions AS (
SELECT * FROM (
SELECT a.*, 
case when linked_mainaudit_id = 0 then fvf_main_audit_id ELSE linked_mainaudit_id END AS submission_id,
concat(b.firstname,' ',b.lastname) AS user_name
 FROM form_via_form_main_audit_answers a LEFT JOIN users b
 ON a.user_id = b.user_id
 ) subq
 WHERE submission_id = @submission_id
)
, cte1 AS (
  SELECT 
    DISTINCT left_node_id AS left_node 
  FROM 
    form_via_form_node_connector 
  WHERE 
    fvf_main_form_id  IN (SELECT distinct fvf_main_form_id FROM form_via_form_main_forms WHERE universal_tag_id = @wfi 	 AND fvf_main_form_id IN (SELECT distinct fvf_main_form_id FROM submissions))
    and left_node_id is not null 
    and left_node_id in ( select distinct fvf_main_form_id from form_via_form_main_forms where deleted_at = 0 and module_id = (select module_id from module) 
)
), 
cte2 AS (
  SELECT 
    DISTINCT cast(typeid AS UNSIGNED) AS right_node 
  FROM 
    form_via_form_node_connector 
  WHERE 
    fvf_main_form_id  IN (SELECT distinct fvf_main_form_id FROM form_via_form_main_forms WHERE universal_tag_id = @wfi AND fvf_main_form_id IN (SELECT distinct fvf_main_form_id FROM submissions))
    AND typeid != '' 
    and typeid in ( select distinct fvf_main_form_id from form_via_form_main_forms where deleted_at = 0 and module_id = (select module_id from module) 
)
), 
cte3 AS (
  SELECT 
    right_node 
  FROM 
    cte2 
  WHERE 
    right_node IN (
      SELECT 
        * 
      FROM 
        cte1
    )
), 
branch AS (
  SELECT 
    distinct right_node AS branch_form 
  FROM 
    cte3 
    LEFT JOIN form_via_form_node_connector t1 ON cte3.right_node = t1.left_node_id 
  WHERE 
    fvf_main_form_id  IN (SELECT distinct fvf_main_form_id FROM form_via_form_main_forms WHERE universal_tag_id = @wfi AND fvf_main_form_id IN (SELECT distinct fvf_main_form_id FROM submissions))
    AND t1.typeID != '' 
    AND t1.typeID IS NOT NULL
),  
root_form AS (
  SELECT 
    distinct left_node AS form
  FROM 
    cte1 
  WHERE 
    left_node NOT IN (
      SELECT 
        * 
      FROM 
        cte2
    )
), 
leaf AS (
  SELECT 
    distinct right_node as leaf_form 
  FROM 
    cte2 
    LEFT JOIN form_via_form_node_connector t1 ON cte2.right_node = t1.typeid 
  where 
    cte2.right_node NOT IN (
      SELECT 
        * 
      FROM 
        branch
    )
), 
root_connections AS (
  SELECT 
    form, 
    fvf_node_connector_id AS connection, 
    ROW_NUMBER() OVER() AS workflow_index
  FROM 
    root_form 
    LEFT JOIN form_via_form_node_connector t1 ON root_form.form = t1.left_node_id 
  WHERE 
    t1.typeid != '' 
    AND t1.typeid IS NOT NULL
), 
branch_connections_toright AS (
  SELECT 
    branch_form, 
    fvf_node_connector_id AS connection 
  FROM 
    branch 
    LEFT JOIN form_via_form_node_connector t1 ON branch.branch_form = t1.left_node_id 
  WHERE 
    t1.typeid != '' 
    AND t1.typeid IS NOT NULL
), 
branch_connections_toleft AS (
  SELECT 
    branch_form, 
    fvf_node_connector_id AS connection 
  FROM 
    branch 
    LEFT JOIN form_via_form_node_connector t1 ON branch.branch_form = t1.typeid
), 
leaf_connections_toleft AS (
  SELECT 
    leaf_form, 
    fvf_node_connector_id AS connection 
  FROM 
    leaf 
    LEFT JOIN form_via_form_node_connector t1 ON leaf.leaf_form = t1.typeid 
), 
all_connections as (
  SELECT 
    form, 
    connection 
  FROM 
    root_connections 
  UNION ALL 
  SELECT 
    * 
  FROM 
    branch_connections_toleft 
  UNION ALL 
  SELECT 
    * 
  FROM 
    branch_connections_toright 
  UNION ALL 
  SELECT 
    * 
  FROM 
    leaf_connections_toleft
) 

