{#
  Use the model's custom schema name (e.g. `staging`, `marts`) directly as the
  BigQuery dataset, instead of dbt's default `<target>_<custom>` concatenation.
#}
{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- if custom_schema_name is none -%}
        {{ target.schema }}
    {%- else -%}
        {{ custom_schema_name | trim }}
    {%- endif -%}
{%- endmacro %}
