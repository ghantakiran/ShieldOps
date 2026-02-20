{{/*
Expand the name of the chart.
*/}}
{{- define "shieldops.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
We truncate at 63 chars because some Kubernetes name fields are limited to this
(by the DNS naming spec). If release name contains chart name it will be used
as a full name.
*/}}
{{- define "shieldops.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "shieldops.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels applied to all resources.
*/}}
{{- define "shieldops.labels" -}}
helm.sh/chart: {{ include "shieldops.chart" . }}
{{ include "shieldops.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels used in matchLabels and service selectors.
*/}}
{{- define "shieldops.selectorLabels" -}}
app.kubernetes.io/name: {{ include "shieldops.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Create the name of the service account to use.
*/}}
{{- define "shieldops.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "shieldops.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

{{/*
Secret name to use (supports existing secret or chart-managed).
*/}}
{{- define "shieldops.secretName" -}}
{{- if .Values.existingSecret }}
{{- .Values.existingSecret }}
{{- else }}
{{- include "shieldops.fullname" . }}-secrets
{{- end }}
{{- end }}

{{/*
ConfigMap name.
*/}}
{{- define "shieldops.configMapName" -}}
{{- include "shieldops.fullname" . }}-config
{{- end }}

{{/*
OPA endpoint URL — resolved at template time so it works in configmap values.
*/}}
{{- define "shieldops.opaEndpoint" -}}
http://{{ include "shieldops.fullname" . }}-opa:8181
{{- end }}
