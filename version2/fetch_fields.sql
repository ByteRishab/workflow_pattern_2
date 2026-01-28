SELECT 
t1.fvf_main_form_id as form_id, 
trim(t1.fvf_main_form_name) as form_name, 
trim(t2.fvf_section_name) as section_name, 
trim(t3.fvf_main_field_name) as field_name, 
trim(t3.fvf_main_field_info) as info1, 
trim(t3.fvf_main_field_info2) as info2, 
trim(t3.fvf_main_field_info3) as info3, 
trim(t3.fvf_main_field_info4) as info4, 
trim(t3.fvf_main_field_info5) as info5

FROM 

form_via_form_main_forms t1 
LEFT JOIN 
form_via_form_main_sections t2 ON 
t1.fvf_main_form_id = t2.fvf_main_form_id
LEFT JOIN 
form_via_form_main_fields t3 ON
t2.fvf_section_id = t3.fvf_section_id

WHERE t1.fvf_main_form_id IN {form_ids}
and t3.deleted_at = 0
and t2.deleted_at = 0
and t1.deleted_at = 0



