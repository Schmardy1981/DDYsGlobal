# DDYs Global Compliance Platform - GCP Deployment Handbuch

**Version:** 1.0
**Letzte Aktualisierung:** 2026-03-17
**Plattform:** Google Cloud Platform (europe-west6, Zuerich)
**Regulatorischer Kontext:** FINMA-konformer Betrieb, Schweizer Datenhaltung

---

## Inhaltsverzeichnis

1. [Voraussetzungen](#1-voraussetzungen)
2. [GCP Projekt Setup](#2-gcp-projekt-setup)
3. [Lokale Entwicklungsumgebung](#3-lokale-entwicklungsumgebung)
4. [Infrastruktur provisionieren](#4-infrastruktur-provisionieren)
5. [MongoDB Atlas Setup](#5-mongodb-atlas-setup)
6. [Container Registry](#6-container-registry)
7. [Secrets konfigurieren](#7-secrets-konfigurieren)
8. [Erster Deployment](#8-erster-deployment)
9. [Tenant Onboarding](#9-tenant-onboarding)
10. [Domain & SSL](#10-domain--ssl)
11. [Monitoring & Alerting](#11-monitoring--alerting)
12. [Backup & Disaster Recovery](#12-backup--disaster-recovery)
13. [Sicherheit & Compliance](#13-sicherheit--compliance)
14. [Kosten](#14-kosten)
15. [Troubleshooting](#15-troubleshooting)
16. [Rollback Verfahren](#16-rollback-verfahren)

---

## 1. Voraussetzungen

### 1.1 Accounts und Zugaenge

| Zugang | Beschreibung | Wo beantragen |
|--------|-------------|---------------|
| GCP Account | Google Cloud Konto mit Billing aktiviert | https://console.cloud.google.com |
| GCP Organisation | Organisation fuer Projekt-Verwaltung | GCP Admin |
| MongoDB Atlas | MongoDB Atlas Account (Organization Owner) | https://cloud.mongodb.com |
| GitHub | Repository-Zugang fuer CI/CD | GitHub Admin |
| Domain-Registrar | DNS-Verwaltung fuer die Domain (z.B. ddys.ch) | Domain-Provider |
| Emergent API | API-Key fuer Claude Sonnet LLM | Emergent Platform |

### 1.2 Erforderliche Berechtigungen

Der ausfuehrende Engineer benoetigt folgende GCP-Rollen:
- `roles/owner` ODER die folgenden einzelnen Rollen:
  - `roles/resourcemanager.projectCreator`
  - `roles/billing.projectManager`
  - `roles/iam.serviceAccountAdmin`
  - `roles/secretmanager.admin`
  - `roles/run.admin`
  - `roles/compute.networkAdmin`
  - `roles/storage.admin`
  - `roles/artifactregistry.admin`
  - `roles/cloudbuild.builds.editor`
  - `roles/monitoring.admin`

### 1.3 Tools (lokal installieren)

| Tool | Mindestversion | Installation |
|------|---------------|-------------|
| gcloud CLI | 450+ | Siehe Abschnitt 3 |
| Terraform | 1.5+ | Siehe Abschnitt 3 |
| Docker Desktop | 24+ | https://docs.docker.com/get-docker/ |
| Python | 3.11+ | https://www.python.org/downloads/ |
| Node.js | 18+ | https://nodejs.org/ |
| Git | 2.40+ | https://git-scm.com/ |

### 1.4 Netzwerk-Anforderungen

- Internetzugang fuer GCP API-Zugriffe
- Port 443 (HTTPS) ausgehend
- Docker Hub Zugang fuer Base-Images (oder Mirror konfigurieren)

---

## 2. GCP Projekt Setup

### 2.1 Projekt erstellen

```bash
# Projekt-ID waehlen (global eindeutig)
export PROJECT_ID="ddys-compliance-prod"
export BILLING_ACCOUNT_ID="01XXXX-XXXXXX-XXXXXX"  # Ihre Billing Account ID

# Projekt erstellen
gcloud projects create $PROJECT_ID \
  --name="DDYs Compliance Platform" \
  --organization="IHRE_ORG_ID"

# Billing verknuepfen
gcloud billing projects link $PROJECT_ID \
  --billing-account=$BILLING_ACCOUNT_ID

# Projekt aktivieren
gcloud config set project $PROJECT_ID
```

**Erwartete Ausgabe:**
```
Create in progress for [https://cloudresourcemanager.googleapis.com/v1/projects/ddys-compliance-prod].
Waiting for [operations/...] to finish...done.
```

**Falls Fehler:** "The caller does not have permission" -> Organisation-Owner muss das Projekt erstellen oder Ihnen die Rolle `roles/resourcemanager.projectCreator` geben.

### 2.2 APIs aktivieren

```bash
gcloud services enable \
  run.googleapis.com \
  compute.googleapis.com \
  secretmanager.googleapis.com \
  artifactregistry.googleapis.com \
  cloudbuild.googleapis.com \
  vpcaccess.googleapis.com \
  cloudresourcemanager.googleapis.com \
  iam.googleapis.com \
  logging.googleapis.com \
  monitoring.googleapis.com \
  cloudtrace.googleapis.com \
  certificatemanager.googleapis.com \
  dns.googleapis.com \
  servicenetworking.googleapis.com
```

**Erwartete Ausgabe:** Fuer jede API:
```
Operation "operations/..." finished successfully.
```

**Dauer:** Ca. 2-3 Minuten fuer alle APIs.

**Falls Fehler:** "Billing is not enabled" -> Billing-Account muss verknuepft sein (Schritt 2.1).

### 2.3 Terraform State Bucket erstellen

Terraform benoetigt einen GCS-Bucket fuer den State. Dieser wird **manuell** erstellt (bevor Terraform laeuft):

```bash
# State-Bucket erstellen (MUSS in europe-west6 sein!)
gcloud storage buckets create "gs://ddys-terraform-state-${PROJECT_ID}" \
  --location=europe-west6 \
  --uniform-bucket-level-access \
  --public-access-prevention

# Versionierung aktivieren (Schutz vor State-Verlust)
gcloud storage buckets update "gs://ddys-terraform-state-${PROJECT_ID}" \
  --versioning
```

**Erwartete Ausgabe:**
```
Creating gs://ddys-terraform-state-ddys-compliance-prod/...
```

---

## 3. Lokale Entwicklungsumgebung

### 3.1 gcloud CLI installieren

**macOS:**
```bash
brew install google-cloud-sdk
```

**Linux (Debian/Ubuntu):**
```bash
curl https://sdk.cloud.google.com | bash
exec -l $SHELL
```

**Windows:** Download von https://cloud.google.com/sdk/docs/install

**Initialisierung:**
```bash
gcloud init
# Waehlen Sie Ihr Projekt aus und setzen Sie die Region:
gcloud config set compute/region europe-west6
gcloud config set compute/zone europe-west6-a
gcloud config set run/region europe-west6
```

**Verifizierung:**
```bash
gcloud config list
# Erwartete Ausgabe:
# [compute]
# region = europe-west6
# zone = europe-west6-a
# [core]
# project = ddys-compliance-prod
```

### 3.2 Terraform installieren

**macOS:**
```bash
brew tap hashicorp/tap
brew install hashicorp/tap/terraform
```

**Linux:**
```bash
wget -O- https://apt.releases.hashicorp.com/gpg | sudo gpg --dearmor -o /usr/share/keyrings/hashicorp-archive-keyring.gpg
echo "deb [signed-by=/usr/share/keyrings/hashicorp-archive-keyring.gpg] https://apt.releases.hashicorp.com $(lsb_release -cs) main" | sudo tee /etc/apt/sources.list.d/hashicorp.list
sudo apt update && sudo apt install terraform
```

**Verifizierung:**
```bash
terraform version
# Terraform v1.x.x
```

### 3.3 Docker konfigurieren

```bash
# Docker fuer GCP Artifact Registry konfigurieren
gcloud auth configure-docker europe-west6-docker.pkg.dev

# Verifizierung
docker pull hello-world
```

### 3.4 Repository klonen

```bash
git clone git@github.com:DDYsGlobal/DDYsGlobal.git
cd DDYsGlobal
```

---

## 4. Infrastruktur provisionieren

### 4.1 Terraform-Variablen vorbereiten

```bash
cd infrastructure/terraform

# Beispiel-Variablen als Grundlage kopieren
cp ../../environments/prod.tfvars terraform.tfvars
```

**terraform.tfvars anpassen** - mindestens diese Werte setzen:

```hcl
project_id  = "ddys-compliance-prod"   # Ihr Projekt-ID aus Schritt 2.1
environment = "prod"

domain_name = "compliance.ddys.ch"     # Ihre Domain

alert_email = "ops@ddys.ch"            # Monitoring-Alerts

github_owner = "DDYsGlobal"            # GitHub Organisation
github_repo  = "DDYsGlobal"            # Repository Name
```

### 4.2 Terraform initialisieren

```bash
terraform init \
  -backend-config="bucket=ddys-terraform-state-${PROJECT_ID}" \
  -backend-config="prefix=terraform/prod"
```

**Erwartete Ausgabe:**
```
Initializing the backend...
Successfully configured the backend "gcs"!
Initializing provider plugins...
- Installing hashicorp/google v5.x.x...
- Installing hashicorp/google-beta v5.x.x...
- Installing hashicorp/random v3.x.x...

Terraform has been successfully initialized!
```

**Falls Fehler:** "Error configuring the backend" -> Pruefen Sie, ob der State-Bucket existiert (Schritt 2.3) und Sie Zugriff haben.

### 4.3 Terraform Plan pruefen

```bash
terraform plan -var-file=terraform.tfvars
```

**Erwartete Ausgabe:** Eine Liste aller Ressourcen, die erstellt werden. Pruefen Sie:
- Alle Ressourcen sind in `europe-west6` (KRITISCH fuer Datenhaltung!)
- Keine unerwarteten Aenderungen an bestehenden Ressourcen
- Die Anzahl der Ressourcen entspricht der Erwartung (~40-50 Ressourcen)

```
Plan: 47 to add, 0 to change, 0 to destroy.
```

### 4.4 Terraform Apply

```bash
terraform apply -var-file=terraform.tfvars
```

Terraform fragt nach Bestaetigung: **yes** eingeben.

**Dauer:** 5-15 Minuten (VPC und Load Balancer brauchen am laengsten).

**Erwartete Ausgabe am Ende:**
```
Apply complete! Resources: 47 added, 0 changed, 0 destroyed.

Outputs:

artifact_registry_url = "europe-west6-docker.pkg.dev/ddys-compliance-prod/ddys-prod"
backend_url = "https://ddys-prod-backend-xxxxxxxxxx-oa.a.run.app"
frontend_url = "https://ddys-prod-frontend-xxxxxxxxxx-oa.a.run.app"
load_balancer_ip = "34.xxx.xxx.xxx"
...
```

**Notieren Sie die Outputs!** Insbesondere:
- `load_balancer_ip` -> fuer DNS-Konfiguration
- `artifact_registry_url` -> fuer Docker-Push
- `backend_url` / `frontend_url` -> fuer Verifizierung

**Falls Fehler bei VPC Connector:** "Serverless VPC Access API has not been used" -> Warten Sie 2-3 Minuten nach API-Aktivierung und fuehren Sie `terraform apply` erneut aus.

**Falls Fehler bei Cloud Armor:** "Requires PAYG or Enterprise" -> Cloud Armor benoetigt moeglicherweise ein erweitertes Billing-Modell. Setzen Sie `cloud_armor_enabled = false` fuer den Anfang.

---

## 5. MongoDB Atlas Setup

### 5.1 Atlas-Cluster in Zuerich erstellen

1. Navigieren Sie zu https://cloud.mongodb.com
2. Erstellen Sie ein neues Projekt: "ddys-compliance-prod"
3. Klicken Sie auf **"Build a Cluster"**

**Cluster-Konfiguration:**
| Einstellung | Wert |
|-------------|------|
| Provider | Google Cloud |
| Region | **Zurich (europe-west6)** - KRITISCH! |
| Cluster Tier | M30 (Production) oder M10 (Development) |
| MongoDB Version | 7.0 |
| Backup | Continuous Backup aktiviert |
| Encryption | Encryption at Rest aktiviert |

4. Klicken Sie auf **"Create Cluster"** (Dauer: 5-10 Minuten)

### 5.2 Datenbank-Benutzer erstellen

1. Unter **Database Access** -> **Add New Database User**
2. Authentication Method: **Password**
3. Username: `ddys-app-prod`
4. Password: Generieren Sie ein starkes Passwort (32+ Zeichen)
5. Database User Privileges: **Read and Write to any database**
6. Restrict to Cluster: Waehlen Sie Ihren Cluster

**Passwort sicher speichern!** Es wird fuer den Connection String benoetigt.

### 5.3 Network Access konfigurieren

**Option A: VPC Peering (empfohlen fuer Produktion)**

1. Unter **Network Access** -> **Peering** -> **Add Peering Connection**
2. Provider: Google Cloud
3. GCP Project ID: Ihr Projekt-ID
4. VPC Network Name: `ddys-prod-vpc` (aus Terraform Output)
5. Atlas CIDR: `192.168.0.0/16` (oder nach Wahl)

Dann in GCP das Peering akzeptieren:
```bash
# Atlas gibt Ihnen einen Peering-Request. Akzeptieren Sie diesen:
gcloud compute networks peerings list --network=ddys-prod-vpc
# Der Peering-Status sollte "ACTIVE" werden
```

**Option B: IP Access List (einfacher, weniger sicher)**

1. Unter **Network Access** -> **IP Access List**
2. Fuegen Sie die Cloud NAT IP-Adresse hinzu (aus GCP Console unter VPC Network -> Cloud NAT)
3. Oder fuer den Anfang: `0.0.0.0/0` (Allow All) - **NUR temporaer!**

### 5.4 Connection String ermitteln

1. Klicken Sie auf **"Connect"** bei Ihrem Cluster
2. Waehlen Sie **"Connect your application"**
3. Driver: Python, Version 3.11
4. Kopieren Sie den Connection String:

```
mongodb+srv://ddys-app-prod:<password>@cluster0.xxxxx.mongodb.net/ddys_prod?retryWrites=true&w=majority
```

Ersetzen Sie `<password>` mit dem Passwort aus Schritt 5.2.

### 5.5 Connection String als Secret speichern

```bash
# MONGO_URL Secret aktualisieren
echo -n "mongodb+srv://ddys-app-prod:IHR_PASSWORT@cluster0.xxxxx.mongodb.net/ddys_prod?retryWrites=true&w=majority" | \
  gcloud secrets versions add ddys-prod-mongo-url \
  --data-file=-

# Verifizierung
gcloud secrets versions access latest --secret=ddys-prod-mongo-url
```

**Erwartete Ausgabe:** Der Connection String (wird angezeigt, nicht teilen!)

---

## 6. Container Registry

### 6.1 Docker-Images bauen

```bash
cd /pfad/zum/DDYsGlobal

# Backend-Image bauen
docker build -f Dockerfile.backend \
  -t europe-west6-docker.pkg.dev/${PROJECT_ID}/ddys-prod/backend:latest \
  .

# Frontend-Image bauen
docker build -f Dockerfile.frontend \
  -t europe-west6-docker.pkg.dev/${PROJECT_ID}/ddys-prod/frontend:latest \
  .
```

**Erwartete Ausgabe (fuer jedes Image):**
```
[+] Building 45.2s (12/12) FINISHED
 => [1/7] FROM python:3.11-slim...
 ...
 => exporting to image
 => => naming to europe-west6-docker.pkg.dev/ddys-compliance-prod/ddys-prod/backend:latest
```

**Dauer:** 2-5 Minuten pro Image (abhaengig von Cache).

### 6.2 Images in Artifact Registry pushen

```bash
# Docker fuer Artifact Registry authentifizieren
gcloud auth configure-docker europe-west6-docker.pkg.dev --quiet

# Backend pushen
docker push europe-west6-docker.pkg.dev/${PROJECT_ID}/ddys-prod/backend:latest

# Frontend pushen
docker push europe-west6-docker.pkg.dev/${PROJECT_ID}/ddys-prod/frontend:latest
```

**Erwartete Ausgabe:**
```
The push refers to repository [europe-west6-docker.pkg.dev/ddys-compliance-prod/ddys-prod/backend]
abc123: Pushed
def456: Pushed
latest: digest: sha256:xxx size: 1234
```

### 6.3 Verifizierung

```bash
# Images in der Registry auflisten
gcloud artifacts docker images list \
  europe-west6-docker.pkg.dev/${PROJECT_ID}/ddys-prod \
  --format='table(IMAGE,TAGS,CREATE_TIME)'
```

---

## 7. Secrets konfigurieren

### 7.1 Uebersicht der erforderlichen Secrets

| Secret ID | Beschreibung | Quelle |
|-----------|-------------|--------|
| `ddys-prod-jwt-secret` | JWT-Signierungsschluessel | Selbst generieren |
| `ddys-prod-mongo-url` | MongoDB Connection String | Atlas (Abschnitt 5.4) |
| `ddys-prod-emergent-llm-key` | Emergent API Key fuer Claude | Emergent Dashboard |

### 7.2 JWT Secret generieren und setzen

```bash
# Sicheren JWT-Secret generieren (64 Zeichen)
JWT_SECRET=$(python3 -c "import secrets; print(secrets.token_urlsafe(48))")
echo "Generated JWT_SECRET: $JWT_SECRET"

# In Secret Manager speichern
echo -n "$JWT_SECRET" | \
  gcloud secrets versions add ddys-prod-jwt-secret \
  --data-file=-
```

**WICHTIG:** Den JWT_SECRET sicher dokumentieren! Bei Verlust werden alle bestehenden Tokens ungueltig und alle Benutzer muessen sich neu anmelden.

### 7.3 MongoDB URL setzen

(Bereits in Abschnitt 5.5 durchgefuehrt)

### 7.4 Emergent LLM Key setzen

```bash
echo -n "IHR_EMERGENT_API_KEY" | \
  gcloud secrets versions add ddys-prod-emergent-llm-key \
  --data-file=-
```

### 7.5 Secrets verifizieren

```bash
# Alle Secrets auflisten
gcloud secrets list --filter="labels.environment=prod" \
  --format='table(NAME,REPLICATION_POLICY,LABELS)'

# Secret-Versionen pruefen (stellt sicher, dass Werte gesetzt sind)
for secret in ddys-prod-jwt-secret ddys-prod-mongo-url ddys-prod-emergent-llm-key; do
  echo "Secret: $secret"
  gcloud secrets versions list $secret --format='table(VERSION_ID,STATE,CREATE_TIME)' --limit=3
  echo ""
done
```

**Erwartete Ausgabe:**
```
Secret: ddys-prod-jwt-secret
VERSION_ID  STATE    CREATE_TIME
2           ENABLED  2026-03-17T10:30:00Z
1           ENABLED  2026-03-17T09:00:00Z
```

---

## 8. Erster Deployment

### 8.1 Automatischer Deployment via Script

Der einfachste Weg:

```bash
cd /pfad/zum/DDYsGlobal
./scripts/deploy.sh prod
```

Das Script fuehrt automatisch aus:
1. Voraussetzungen pruefen
2. Terraform init/plan/apply
3. Docker-Images bauen und pushen
4. Cloud Run deployen
5. Datenbank seeden
6. Health-Check

### 8.2 Manuelles Deployment (Schritt fuer Schritt)

Falls das automatische Script nicht verwendet wird:

#### a) Cloud Run Backend deployen

```bash
gcloud run deploy ddys-prod-backend \
  --image=europe-west6-docker.pkg.dev/${PROJECT_ID}/ddys-prod/backend:latest \
  --region=europe-west6 \
  --platform=managed \
  --service-account=ddys-prod-run-sa@${PROJECT_ID}.iam.gserviceaccount.com \
  --set-env-vars="ENVIRONMENT=production,GCP_PROJECT_ID=${PROJECT_ID},GCP_REGION=europe-west6,STORAGE_TYPE=gcs,LOG_FORMAT=json" \
  --set-secrets="JWT_SECRET=ddys-prod-jwt-secret:latest,MONGO_URL=ddys-prod-mongo-url:latest,EMERGENT_LLM_KEY=ddys-prod-emergent-llm-key:latest" \
  --min-instances=2 \
  --max-instances=20 \
  --cpu=2 \
  --memory=2Gi \
  --concurrency=80 \
  --timeout=300 \
  --vpc-connector=ddys-prod-connector \
  --vpc-egress=private-ranges-only \
  --ingress=internal-and-cloud-load-balancing \
  --allow-unauthenticated \
  --quiet
```

#### b) Cloud Run Frontend deployen

```bash
gcloud run deploy ddys-prod-frontend \
  --image=europe-west6-docker.pkg.dev/${PROJECT_ID}/ddys-prod/frontend:latest \
  --region=europe-west6 \
  --platform=managed \
  --service-account=ddys-prod-run-sa@${PROJECT_ID}.iam.gserviceaccount.com \
  --min-instances=2 \
  --max-instances=10 \
  --cpu=1 \
  --memory=512Mi \
  --concurrency=200 \
  --ingress=internal-and-cloud-load-balancing \
  --allow-unauthenticated \
  --quiet
```

### 8.3 Health-Check

```bash
# Backend-URL ermitteln
BACKEND_URL=$(gcloud run services describe ddys-prod-backend \
  --region=europe-west6 --format='value(status.url)')
echo "Backend: $BACKEND_URL"

# Health-Check
curl -s "${BACKEND_URL}/api/health" | python3 -m json.tool
```

**Erwartete Ausgabe:**
```json
{
    "status": "healthy",
    "service": "ddys-compliance",
    "periodic_jobs": {
        "status": "running"
    }
}
```

### 8.4 Initiales Seeding

```bash
# Demo-Daten seeden
curl -s -X POST "${BACKEND_URL}/api/seed" | python3 -m json.tool
```

**Erwartete Ausgabe:**
```json
{
    "message": "Demo data seeded successfully",
    "tenant_id": "demo-bank-xxx"
}
```

### 8.5 Deployment-Checkliste

- [ ] Backend Health-Check: HTTP 200
- [ ] Frontend erreichbar: HTTP 200
- [ ] MongoDB-Verbindung: Health-Check zeigt "healthy"
- [ ] Secrets geladen: Kein "CHANGE_ME" in den Logs
- [ ] Load Balancer IP: Notiert fuer DNS
- [ ] SSL-Zertifikat: Status pruefen (kann 24h dauern)
- [ ] Monitoring-Alerts: Email-Benachrichtigung konfiguriert

---

## 9. Tenant Onboarding

### 9.1 Automatisiertes Onboarding

```bash
./scripts/setup-tenant.sh "swiss-trust-ag" "Swiss Trust AG" "admin@swisstrust.ch" prod
```

**Erwartete Ausgabe:**
```
=================================================================
  TENANT PROVISIONING COMPLETE
=================================================================
  Tenant ID:       swiss-trust-ag
  Tenant Name:     Swiss Trust AG
  Admin Email:     admin@swisstrust.ch
  Environment:     prod
  ...
  Resources Created:
    - GCS Bucket:  ddys-prod-swiss-trust-ag-documents
    - Secret:      ddys-prod-tenant-swiss-trust-ag-api-key
```

### 9.2 Manuelles Onboarding

Falls das Script nicht verwendet wird:

#### a) GCS-Bucket erstellen

```bash
TENANT_ID="swiss-trust-ag"

gcloud storage buckets create "gs://ddys-prod-${TENANT_ID}-documents" \
  --location=europe-west6 \
  --uniform-bucket-level-access \
  --default-storage-class=STANDARD

gcloud storage buckets update "gs://ddys-prod-${TENANT_ID}-documents" \
  --versioning
```

#### b) IAM-Berechtigung setzen

```bash
gcloud storage buckets add-iam-policy-binding \
  "gs://ddys-prod-${TENANT_ID}-documents" \
  --member="serviceAccount:ddys-prod-run-sa@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/storage.objectUser"
```

#### c) Tenant in der Anwendung anlegen

1. Einloggen als GLOBAL_SUPER_ADMIN
2. Navigation: Admin > Tenants > Neuer Tenant
3. Formular ausfuellen:
   - Tenant ID: `swiss-trust-ag`
   - Name: `Swiss Trust AG`
   - Admin E-Mail: `admin@swisstrust.ch`
4. Speichern

### 9.3 Tenant-Isolation verifizieren

Nach dem Onboarding pruefen:

```bash
# Bucket existiert
gcloud storage ls gs://ddys-prod-${TENANT_ID}-documents/

# Bucket ist in Zuerich
gcloud storage buckets describe gs://ddys-prod-${TENANT_ID}-documents \
  --format='value(location)'
# Erwartete Ausgabe: EUROPE-WEST6
```

---

## 10. Domain & SSL

### 10.1 DNS-Konfiguration

Ermitteln Sie die Load-Balancer-IP:

```bash
cd infrastructure/terraform
terraform output load_balancer_ip
# Ausgabe: 34.xxx.xxx.xxx
```

Erstellen Sie beim DNS-Provider folgende Eintraege:

| Typ | Name | Wert | TTL |
|-----|------|------|-----|
| A | compliance.ddys.ch | 34.xxx.xxx.xxx | 300 |
| CNAME | www.compliance.ddys.ch | compliance.ddys.ch | 300 |

### 10.2 SSL-Zertifikat

Das SSL-Zertifikat wird automatisch von Google verwaltet (erstellt in `load_balancer.tf`).

**Status pruefen:**

```bash
gcloud compute ssl-certificates describe ddys-prod-ssl-cert \
  --global \
  --format='table(NAME,TYPE,MANAGED_STATUS,DOMAIN_STATUS)'
```

**Erwartete Ausgabe nach DNS-Propagation:**
```
NAME                TYPE     MANAGED_STATUS  DOMAIN_STATUS
ddys-prod-ssl-cert  MANAGED  ACTIVE         compliance.ddys.ch: ACTIVE
```

**WICHTIG:** Das Zertifikat wird erst "ACTIVE", wenn:
1. DNS korrekt konfiguriert ist (A-Record zeigt auf LB-IP)
2. DNS-Propagation abgeschlossen ist (kann bis zu 24 Stunden dauern)

**Falls Status "PROVISIONING":**
- Warten Sie bis zu 24 Stunden
- Pruefen Sie DNS: `dig compliance.ddys.ch` -> muss die LB-IP zurueckgeben
- Falls nach 24h noch "PROVISIONING": DNS-Konfiguration pruefen

### 10.3 HTTPS erzwingen

Die Terraform-Konfiguration erstellt automatisch eine HTTP->HTTPS-Umleitung. Pruefen Sie:

```bash
curl -I http://compliance.ddys.ch
# Erwartete Ausgabe:
# HTTP/1.1 301 Moved Permanently
# Location: https://compliance.ddys.ch/
```

---

## 11. Monitoring & Alerting

### 11.1 Cloud Monitoring Dashboard

Das Dashboard wird automatisch von Terraform erstellt. Zugriff:

1. https://console.cloud.google.com/monitoring/dashboards
2. Dashboard: "DDYs prod - Compliance Platform"

**Enthaltene Metriken:**
- Request Count (pro Sekunde)
- Request Latency (p50, p95, p99)
- Instance Count (Auto-Scaling)
- CPU & Memory Utilization
- Error Logs (Echtzeit)

### 11.2 Alert-Konfiguration

Automatisch konfigurierte Alerts (via Terraform):

| Alert | Bedingung | Dauer |
|-------|----------|-------|
| High Error Rate | >5% 5xx-Fehler | 5 Min |
| High Latency | p99 > 5s | 5 Min |
| Near Max Instances | >80% der max Instanzen | 5 Min |
| Backend Down | Uptime-Check fehlgeschlagen | 2 Min |

### 11.3 Slack-Integration (optional)

```bash
# Slack Notification Channel erstellen
gcloud monitoring notification-channels create \
  --display-name="DDYs Prod Slack" \
  --type=slack \
  --channel-labels=channel_name="#ddys-alerts" \
  --channel-labels=auth_token="xoxb-SLACK-TOKEN"
```

### 11.4 Log-basierte Alerts

Zusaetzliche Alerts koennen ueber Log-Filter erstellt werden:

```bash
# Beispiel: Alert bei Security-Events
gcloud logging metrics create ddys-security-events \
  --description="Security-relevante Events" \
  --filter='resource.type="cloud_run_revision" AND jsonPayload.severity="critical"' \
  --project=$PROJECT_ID
```

---

## 12. Backup & Disaster Recovery

### 12.1 MongoDB Atlas Backup

Atlas bietet automatische Backups. Konfiguration:

1. Atlas Console -> Cluster -> Backup
2. **Continuous Backup**: Aktiviert (Point-in-Time Recovery)
3. **Snapshot Schedule**:
   - Stuendlich: 24 Stunden aufbewahren
   - Taeglich: 7 Tage aufbewahren
   - Woechentlich: 4 Wochen aufbewahren
   - Monatlich: 12 Monate aufbewahren

**Restore testen:**
```
Atlas Console -> Backup -> Restore -> "Download" oder "Restore to Cluster"
```

### 12.2 GCS Document Backup

Dokumente in GCS sind automatisch versioniert. Zusaetzlich:

```bash
# Backup-Bucket wird von Terraform erstellt: ddys-prod-backups-xxx
# Regelmaessiges Kopieren kritischer Daten:
gcloud storage cp -r \
  "gs://ddys-prod-documents-xxx/tenants/" \
  "gs://ddys-prod-backups-xxx/documents-backup-$(date +%Y%m%d)/"
```

**Automatisierung via Cloud Scheduler:**

```bash
gcloud scheduler jobs create http backup-documents-daily \
  --schedule="0 2 * * *" \
  --uri="https://ddys-prod-backend-xxx.run.app/api/admin/backup" \
  --http-method=POST \
  --time-zone="Europe/Zurich" \
  --location=europe-west6
```

### 12.3 RTO/RPO

| Komponente | RPO | RTO | Strategie |
|-----------|-----|-----|-----------|
| MongoDB | 1 Stunde (Continuous) | 1-4 Stunden | Atlas Point-in-Time Restore |
| Dokumente (GCS) | 0 (versioniert) | Minuten | GCS Object Versioning |
| Anwendung (Cloud Run) | 0 (immutable) | Minuten | Revision Rollback |
| Secrets | 0 (versioniert) | Minuten | Secret Manager Versioning |
| Infrastructure | 0 (IaC) | 30-60 Min | Terraform re-apply |

### 12.4 Disaster Recovery Test

Fuehren Sie quartalsweise einen DR-Test durch:

1. **MongoDB Restore Test**: Stellen Sie einen Snapshot in einem Test-Cluster wieder her
2. **GCS Restore Test**: Stellen Sie eine alte Objektversion wieder her
3. **Cloud Run Rollback**: Fuehren Sie ein Rollback auf eine vorherige Revision durch
4. **Full Redeploy**: Terraform destroy + apply in einer Test-Umgebung

---

## 13. Sicherheit & Compliance

### 13.1 Schweizer Datenhaltung (FINMA)

**Alle Daten muessen in der Schweiz bleiben.** Folgende Massnahmen stellen dies sicher:

| Komponente | Standort | Verifizierung |
|-----------|---------|--------------|
| Cloud Run | europe-west6 | `gcloud run services describe ... --format='value(metadata.labels.cloud.googleapis.com/location)'` |
| GCS Buckets | europe-west6 | `gcloud storage buckets describe gs://... --format='value(location)'` |
| Secrets | europe-west6 | Terraform: user_managed replication mit location europe-west6 |
| MongoDB Atlas | GCP Zurich | Atlas Console: Cluster Region |
| Cloud Logging | Europe | GCP Standard fuer europe-west6 Projekte |
| Terraform State | europe-west6 | State-Bucket Location |

**Verifizierungs-Script:**

```bash
echo "=== Datenhaltungs-Verifizierung ==="

echo "Cloud Run Backend:"
gcloud run services describe ddys-prod-backend --region=europe-west6 \
  --format='value(metadata.labels.cloud.googleapis.com/location)'

echo "GCS Buckets:"
for bucket in $(gcloud storage ls | grep ddys-prod); do
  loc=$(gcloud storage buckets describe $bucket --format='value(location)')
  echo "  $bucket -> $loc"
done

echo "Secrets:"
for secret in $(gcloud secrets list --filter="labels.environment=prod" --format='value(NAME)'); do
  loc=$(gcloud secrets describe $secret --format='value(replication.userManaged.replicas[0].location)')
  echo "  $secret -> $loc"
done
```

### 13.2 Verschluesselung

- **At Rest:** Alle GCP-Dienste verschluesseln Daten at-rest standardmaessig (AES-256)
- **In Transit:** TLS 1.2+ erzwungen (SSL Policy in `load_balancer.tf`)
- **MongoDB:** Atlas bietet Encryption at Rest und in Transit

### 13.3 Zugriffskontrolle

- **Service Accounts:** Least Privilege (nur notwendige Rollen)
- **IAM:** Keine `roles/owner` fuer Service Accounts
- **Cloud Armor:** WAF-Regeln gegen OWASP Top 10
- **Tenant Isolation:** Middleware prueft jede Anfrage auf Tenant-Zugehoerigkeit

### 13.4 Audit-Trail

Das System protokolliert:
- Alle Benutzeraktionen (Login, Dokumenten-Upload, Genehmigungen)
- Cross-Tenant-Zugriffversuche
- API-Fehler und Sicherheitsereignisse
- Administrative Aenderungen

Audit-Logs sind in MongoDB gespeichert UND in Cloud Logging (strukturiert).

---

## 14. Kosten

### 14.1 Geschaetzte monatliche Kosten (Production)

| Dienst | Konfiguration | Geschaetzte Kosten/Monat (CHF) |
|--------|--------------|-------------------------------|
| Cloud Run Backend | 2 vCPU, 2 GiB, 2 Min-Instanzen | 150-300 |
| Cloud Run Frontend | 1 vCPU, 512 MiB, 2 Min-Instanzen | 50-100 |
| Cloud Load Balancer | Global HTTPS LB | 25-50 |
| Cloud Armor | WAF-Regeln | 15-30 |
| GCS Storage | ~100 GB Dokumente | 5-15 |
| Secret Manager | ~10 Secrets, moderate Zugriffe | 1-5 |
| Cloud Logging | ~50 GB/Monat | 25-50 |
| Cloud Monitoring | Custom Metrics + Dashboards | 10-30 |
| Artifact Registry | ~5 Images, ~2 GB | 1-5 |
| VPC/Networking | VPC Connector, NAT | 30-50 |
| MongoDB Atlas | M30, Zurich | 350-500 |
| **Gesamt** | | **~650-1'150 CHF/Monat** |

### 14.2 Kostenoptimierung

- **Dev/Staging:** `min_instances = 0` (Scale-to-Zero, ca. 80% Ersparnis)
- **Cloud Run CPU Idle:** In nicht-produktiven Umgebungen `cpu_idle = true`
- **GCS Lifecycle:** Archivierung nach 10 Jahren reduziert Speicherkosten um 90%
- **Reservierte Kapazitaet:** Fuer MongoDB Atlas Committed Use Discounts pruefen

### 14.3 Budget-Alerts

```bash
# Budget-Alert einrichten (manuell in GCP Console)
# Billing -> Budgets & alerts -> Create Budget
# Betrag: 1500 CHF/Monat
# Schwellenwerte: 50%, 80%, 100%
# Benachrichtigung: ops@ddys.ch
```

---

## 15. Troubleshooting

### 15.1 Cloud Run startet nicht

**Symptom:** Service Status "Failed" oder Deployment haengt

**Diagnose:**
```bash
# Logs ansehen
gcloud run services logs read ddys-prod-backend --region=europe-west6 --limit=50

# Revision-Status pruefen
gcloud run revisions list --service=ddys-prod-backend --region=europe-west6
```

**Haeufige Ursachen:**
| Fehler | Loesung |
|--------|---------|
| "Container failed to start" | Startup Probe Timeout erhoehen, Port pruefen (8000) |
| "Secret not found" | Secret existiert? Version ENABLED? IAM korrekt? |
| "Memory limit exceeded" | Memory erhoehen (z.B. 2Gi -> 4Gi) |
| "Connection refused to MongoDB" | MONGO_URL pruefen, VPC Peering pruefen, Atlas Network Access pruefen |

### 15.2 502 Bad Gateway

**Symptom:** Load Balancer gibt 502 zurueck

**Diagnose:**
```bash
# Backend-Service direkt pruefen
BACKEND_URL=$(gcloud run services describe ddys-prod-backend \
  --region=europe-west6 --format='value(status.url)')
curl -v "${BACKEND_URL}/api/health"

# Load Balancer Logs
gcloud logging read 'resource.type="http_load_balancer" AND httpRequest.status=502' \
  --limit=10 --format=json
```

**Loesung:**
- Backend-Instanzen laufen? (`gcloud run services describe ...`)
- Health-Check-Pfad korrekt? (`/api/health`)
- Backend-Image korrekt? (Artifact Registry pruefen)

### 15.3 Langsame Antwortzeiten

**Symptom:** API-Antworten dauern >3 Sekunden

**Diagnose:**
```bash
# Cloud Trace pruefen
# https://console.cloud.google.com/traces?project=$PROJECT_ID

# Cold-Start pruefen
gcloud run services describe ddys-prod-backend --region=europe-west6 \
  --format='value(spec.template.spec.containerConcurrency)'
```

**Loesung:**
- `min_instances` erhoehen (vermeidet Cold Starts)
- `startup_cpu_boost` aktiviert? (in Terraform: ja)
- MongoDB-Indizes pruefen
- VPC Connector Kapazitaet erhoehen

### 15.4 Dokument-Upload schlaegt fehl

**Symptom:** 500 bei POST /api/documents/upload

**Diagnose:**
```bash
# Logs filtern
gcloud logging read \
  'resource.type="cloud_run_revision" AND
   resource.labels.service_name="ddys-prod-backend" AND
   jsonPayload.message=~"upload|GCS|storage"' \
  --limit=20

# GCS-Bucket Zugriff testen
gcloud storage ls gs://ddys-prod-documents-xxx/
```

**Haeufige Ursachen:**
| Fehler | Loesung |
|--------|---------|
| "Bucket not found" | Bucket-Name in GCS_BUCKET_PREFIX pruefen |
| "Access denied" | Service Account IAM-Rollen pruefen |
| "File too large" | MAX_FILE_SIZE_BYTES in storage.py (20 MB Standard) |
| "MIME type not allowed" | ALLOWED_MIME_TYPES in storage.py pruefen |

### 15.5 Cross-Tenant-Zugriffsfehler

**Symptom:** 403 "Access denied: you cannot access data belonging to another tenant"

Das ist **erwuenschtes Verhalten** - die Tenant-Isolation funktioniert korrekt.

**Falls ein berechtigter Zugriff blockiert wird:**
- Pruefen Sie die User-Rolle (`global_role` muss `GLOBAL_SUPER_ADMIN` oder `DDYS_COMPLIANCE_MANAGER` sein)
- Pruefen Sie den `tenant_id` im JWT-Token

### 15.6 Terraform State Lock

**Symptom:** "Error acquiring the state lock"

```bash
# State Lock manuell aufheben (NUR wenn sicher, dass kein anderer Terraform laeuft!)
terraform force-unlock LOCK_ID
```

---

## 16. Rollback Verfahren

### 16.1 Automatisches Rollback

```bash
# Interaktives Rollback
./scripts/rollback.sh prod

# Backend auf vorherige Version zuruecksetzen
./scripts/rollback.sh prod backend

# Auf spezifische Revision zuruecksetzen
./scripts/rollback.sh prod backend ddys-prod-backend-00042-xxx
```

### 16.2 Manuelles Rollback

#### a) Verfuegbare Revisionen auflisten

```bash
gcloud run revisions list \
  --service=ddys-prod-backend \
  --region=europe-west6 \
  --format='table(REVISION,ACTIVE,DEPLOYED,STATUS)' \
  --sort-by='~DEPLOYED' \
  --limit=10
```

**Erwartete Ausgabe:**
```
REVISION                          ACTIVE  DEPLOYED              STATUS
ddys-prod-backend-00045-abc       yes     2026-03-17T14:00:00Z  Ready
ddys-prod-backend-00044-def       no      2026-03-16T10:00:00Z  Ready
ddys-prod-backend-00043-ghi       no      2026-03-15T09:00:00Z  Ready
```

#### b) Traffic auf vorherige Revision umleiten

```bash
# 100% Traffic auf die vorherige Revision
gcloud run services update-traffic ddys-prod-backend \
  --region=europe-west6 \
  --to-revisions=ddys-prod-backend-00044-def=100
```

#### c) Canary Rollback (schrittweise)

```bash
# Erst 10% auf die alte Version
gcloud run services update-traffic ddys-prod-backend \
  --region=europe-west6 \
  --to-revisions=ddys-prod-backend-00044-def=10,ddys-prod-backend-00045-abc=90

# Nach Verifizierung: 50/50
gcloud run services update-traffic ddys-prod-backend \
  --region=europe-west6 \
  --to-revisions=ddys-prod-backend-00044-def=50,ddys-prod-backend-00045-abc=50

# Komplett zurueck
gcloud run services update-traffic ddys-prod-backend \
  --region=europe-west6 \
  --to-revisions=ddys-prod-backend-00044-def=100
```

### 16.3 Datenbank-Rollback

Falls eine Datenbank-Migration fehlgeschlagen ist:

1. **MongoDB Atlas Restore:**
   - Atlas Console -> Cluster -> Backup
   - Waehlen Sie einen Zeitpunkt VOR der fehlerhaften Migration
   - "Restore to this cluster" (VORSICHT: ueberschreibt aktuelle Daten!)

2. **Oder: Point-in-Time Recovery:**
   - Atlas Console -> Backup -> Point in Time Restore
   - Waehlen Sie einen Zeitpunkt mit Sekundengenauigkeit

### 16.4 Infrastruktur-Rollback

Falls Terraform-Aenderungen Probleme verursachen:

```bash
# Vorherige State-Version wiederherstellen
gcloud storage objects list \
  "gs://ddys-terraform-state-${PROJECT_ID}/terraform/prod/" \
  --format='value(name,generation,updated)' \
  --sort-by='~updated' \
  --limit=5

# Alte Version wiederherstellen
gcloud storage cp \
  "gs://ddys-terraform-state-${PROJECT_ID}/terraform/prod/default.tfstate#GENERATION_ID" \
  "gs://ddys-terraform-state-${PROJECT_ID}/terraform/prod/default.tfstate"

# Dann terraform apply mit den gewuenschten Variablen
terraform apply -var-file=terraform.tfvars
```

### 16.5 Rollback-Checkliste

Nach jedem Rollback:

- [ ] Health-Check: Backend und Frontend erreichbar
- [ ] Funktionstest: Login, Case erstellen, Dokument hochladen
- [ ] Logs pruefen: Keine neuen Fehler
- [ ] Monitoring: Metriken normalisiert
- [ ] Team informieren: Rollback-Grund und Status kommunizieren
- [ ] Post-Mortem: Ursache dokumentieren und Massnahmen definieren

---

## Anhang

### A. Nuetzliche Befehle

```bash
# Cloud Run Logs live verfolgen
gcloud run services logs tail ddys-prod-backend --region=europe-west6

# Alle Cloud Run Services auflisten
gcloud run services list --region=europe-west6

# GCS-Speicherverbrauch pro Bucket
gcloud storage du -s gs://ddys-prod-documents-xxx/

# Secret-Wert anzeigen (VORSICHT!)
gcloud secrets versions access latest --secret=ddys-prod-jwt-secret

# Service Account Berechtigungen pruefen
gcloud projects get-iam-policy $PROJECT_ID \
  --filter="bindings.members:ddys-prod-run-sa" \
  --format='table(bindings.role)'
```

### B. Kontakte

| Rolle | Kontakt |
|-------|---------|
| DevOps/Infrastructure | ops@ddys.ch |
| Security | security@ddys.ch |
| MongoDB Atlas Support | https://support.mongodb.com |
| GCP Support | https://console.cloud.google.com/support |

### C. Aenderungsprotokoll

| Datum | Version | Aenderung | Autor |
|-------|---------|-----------|-------|
| 2026-03-17 | 1.0 | Initiale Version | DDYs Engineering |
