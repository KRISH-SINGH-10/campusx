# Build and deploy to Cloud Run (Mumbai).
#   .\deploy.ps1           private service (sign-in required)
#   .\deploy.ps1 -Public   public URL for judges
param([switch]$Public)

$gcloud = "$env:LOCALAPPDATA\Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd"
# Without -Public the current access setting is left as it is.
$access = if ($Public) { @("--allow-unauthenticated") } else { @() }

& $gcloud run deploy campusx `
  --source $PSScriptRoot `
  --project hackathon-511418 `
  --region asia-south1 `
  --memory 1Gi `
  --min-instances 1 `
  --set-env-vars "GOOGLE_CLOUD_PROJECT=hackathon-511418" `
  @access `
  --quiet

