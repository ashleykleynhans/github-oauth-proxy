variable "REGISTRY_USER" {
    default = "ashleykleynhans"
}

variable "APP" {
    default = "github-oauth-proxy"
}

group "default" {
    targets = ["github-oauth-proxy"]
}

# Empty target inherited by the image target so that CI can merge tags and
# labels into it from docker/metadata-action's bake-file output.
target "docker-metadata-action" {}

target "github-oauth-proxy" {
    inherits = ["docker-metadata-action"]
    dockerfile = "Dockerfile"
    attest = [
        "type=provenance,mode=min",
        "type=sbom"
    ]
    labels = {
        "org.opencontainers.image.title" = "GitHub OAuth2 Proxy for Spinnaker"
        "org.opencontainers.image.description" = "GitHub OAuth2 proxy for Spinnaker that enforces GitHub organization and email domain requirements."
        "org.opencontainers.image.source" = "https://github.com/${REGISTRY_USER}/${APP}"
        "org.opencontainers.image.licenses" = "GPL-3.0"
    }
}
