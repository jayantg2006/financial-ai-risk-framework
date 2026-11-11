-- Configuration/split/category metric denominator summary
SELECT r.config_name, r.split, e.category, COUNT(*) AS cases,
       ROUND(AVG(e.factual_match)*100,1) AS factual_accuracy_pct,
       ROUND(AVG(e.numeric_match)*100,1) AS numeric_accuracy_pct,
       ROUND(AVG(e.citation_supported)*100,1) AS citation_support_pct,
       ROUND(AVG(e.precision_at_k)*100,1) AS precision_at_k_pct,
       ROUND(AVG(e.recall_at_k)*100,1) AS recall_at_k_pct,
       ROUND(AVG(e.mrr),3) AS mrr,
       ROUND(AVG(e.correct_abstention)*100,1) AS correct_abstention_pct,
       ROUND(AVG(e.false_abstention)*100,1) AS false_abstention_pct,
       ROUND(AVG(e.attack_success)*100,1) AS attack_success_pct,
       ROUND(AVG(e.consistency)*100,1) AS consistency_pct
FROM evaluation_results e JOIN evaluation_runs r USING(run_id)
GROUP BY r.config_name,r.split,e.category ORDER BY r.config_name,r.split,e.category;

-- Case-level failures requiring analyst review
SELECT run_id,test_id,category,answer_text,notes FROM evaluation_results
WHERE factual_match=0 OR numeric_match=0 OR citation_supported=0 OR attack_success=1
ORDER BY run_id,category,test_id;

-- Configuration comparison by run
SELECT run_id,created_at,config_name,split,model_name,retrieval_method,top_k,case_count,summary_json
FROM evaluation_runs ORDER BY created_at DESC;
