{{/*
Expand the name of the chart.
*/}}
{{- define "rag.name" -}}
rag-multi-expert
{{- end }}

{{/*
Create chart name and version.
*/}}
{{- define "rag.chart" -}}
{{ .Chart.Name }}-{{ .Chart.Version | replace "+" "_" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "rag.labels" -}}
helm.sh/chart: {{ include "rag.chart" . }}
app.kubernetes.io/name: {{ include "rag.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "rag.selectorLabels" -}}
app.kubernetes.io/name: {{ include "rag.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}