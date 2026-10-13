-- Public comparison: copy the existing exported score, never recompute it.
ALTER TABLE public.catalog_search ADD COLUMN IF NOT EXISTS quality_score_v4_100 double precision
  CHECK (quality_score_v4_100 BETWEEN 0 AND 100);
CREATE OR REPLACE VIEW public.catalog_search_current
  WITH (security_invoker = true) AS
SELECT cs.catalog_version,
       cs.dsld_id,
       cs.product_name,
       cs.brand_name,
       cs.brand_family,
       cs.product_line,
       cs.upc_sku,
       cs.form_factor,
       cs.supplement_type,
       cs.product_status,
       cs.quality_tier,
       cs.quality_score_status,
       cs.product_safety_status,
       cs.mapped_coverage,
       cs.quality_score_confidence,
       cs.quality_assessment_status,
       cs.search_tsv,
       cs.quality_score_v4_100
  FROM public.catalog_search cs
  JOIN public.export_manifest m
    ON m.db_version = cs.catalog_version
   AND m.is_current = true;

REVOKE ALL ON TABLE public.catalog_search_current FROM PUBLIC, anon, authenticated;
GRANT SELECT ON TABLE public.catalog_search_current TO service_role;
-- security_invoker view: its reader also needs the manifest it joins.
GRANT SELECT ON TABLE public.export_manifest TO service_role;


DROP FUNCTION IF EXISTS public.search_catalog(text, text, text, integer);
CREATE OR REPLACE FUNCTION public.search_catalog(
  p_query text,
  p_brand text DEFAULT NULL,
  p_form  text DEFAULT NULL,
  p_limit integer DEFAULT 10,
  p_sort text DEFAULT 'relevance',
  p_offset integer DEFAULT 0,
  p_catalog_version text DEFAULT NULL,
  p_supplement_type text DEFAULT NULL
)
RETURNS TABLE (
  catalog_version          text,
  dsld_id                  text,
  product_name             text,
  brand_name               text,
  brand_family             text,
  product_line             text,
  upc_sku                  text,
  form_factor              text,
  supplement_type          text,
  product_status           text,
  quality_tier             text,
  quality_score_status     text,
  product_safety_status    text,
  mapped_coverage          double precision,
  quality_score_confidence text,
  quality_assessment_status text,
  match_score              real,
  quality_score_v4_100     double precision,
  total_matches           bigint
)
LANGUAGE sql STABLE SECURITY INVOKER
SET search_path = public, extensions, pg_catalog
AS $$
  WITH q AS (
    SELECT lower(left(btrim(coalesce(p_query, '')), 200)) AS text,
           websearch_to_tsquery('simple'::regconfig, left(btrim(coalesce(p_query, '')), 200)) AS tsq
  )
  SELECT c.catalog_version, c.dsld_id, c.product_name, c.brand_name, c.brand_family,
         c.product_line, c.upc_sku, c.form_factor, c.supplement_type, c.product_status,
         c.quality_tier, c.quality_score_status, c.product_safety_status,
         c.mapped_coverage, c.quality_score_confidence, c.quality_assessment_status,
         LEAST(1.0,
           GREATEST(
             extensions.similarity(c.product_name, q.text),
             extensions.word_similarity(
               q.text, concat_ws(' ', c.brand_name, c.product_name, c.product_line))
           ) * 0.8
           + ts_rank_cd(c.search_tsv, q.tsq, 32) * 0.2
         )::real AS match_score,
         c.quality_score_v4_100, count(*) OVER () AS total_matches
    FROM public.catalog_search_current c, q
   WHERE length(q.text) > 0
     AND p_sort IN ('relevance', 'quality')
     AND (p_supplement_type IS NULL OR c.supplement_type = p_supplement_type)
     AND (p_catalog_version IS NULL OR c.catalog_version = p_catalog_version)
     AND (c.search_tsv @@ q.tsq OR q.text <% c.product_name OR q.text <% c.brand_name)
     AND (p_brand IS NULL OR strpos(lower(concat_ws(' ', c.brand_name, c.brand_family)),
                                    lower(btrim(p_brand))) > 0)
     AND (p_form IS NULL OR strpos(lower(coalesce(c.form_factor, '')), lower(btrim(p_form))) > 0)
   ORDER BY CASE WHEN p_sort = 'quality' AND c.quality_score_status = 'scored'
                       AND c.quality_assessment_status = 'complete'
                 THEN c.quality_score_v4_100 END DESC NULLS LAST,
            match_score DESC, c.dsld_id
   LIMIT LEAST(GREATEST(coalesce(p_limit, 10), 1), 25)
   OFFSET GREATEST(coalesce(p_offset, 0), 0);
$$;

REVOKE ALL ON FUNCTION public.search_catalog(text, text, text, integer, text, integer, text, text)
  FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.search_catalog(text, text, text, integer, text, integer, text, text)
  TO service_role;
