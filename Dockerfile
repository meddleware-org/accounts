# The Meddleware identity provider image: upstream Keycloak with its build-time options baked in (ADR-0016, FU-0194).
#
# Why an optimised image: the pod runs with a read-only root filesystem, and `start --optimized` writes nothing outside /tmp and the data directory
# (both emptyDir volumes), whereas a plain `start` re-augments Keycloak on every boot and needs a writable /opt/keycloak (proved by the spike,
# k8s/base/auth/tests/keycloak-spike in the Meddleware workspace). Run it with: start --optimized, plus the runtime options as KC_* variables.

# The upstream image, pinned by digest (the exact bytes are fixed; Dependabot moves the pin). quay.io/keycloak/keycloak publishes no cosign signature, so
# the digest pin plus the Trivy scan of the result in CI is the control.
FROM quay.io/keycloak/keycloak:26.8.2@sha256:75b5c435a83b530caba5923922f93d47b2e3f8b4ad9e79200581122996653e55

# OCI labels: who built this and from what (the release workflow overrides VERSION).
ARG VERSION=dev
LABEL org.opencontainers.image.title="accounts" \
      org.opencontainers.image.description="Keycloak with build-time options baked in, for the Meddleware identity layer" \
      org.opencontainers.image.source="https://github.com/meddleware-org/accounts" \
      org.opencontainers.image.licenses="0BSD" \
      org.opencontainers.image.version="${VERSION}"

# Build-time options only: the database vendor (PostgreSQL), and the health and metrics endpoints on the management port. Everything else (database
# URL, hostname, proxy headers, the bootstrap admin) is a runtime option, so one image serves every instance.
RUN /opt/keycloak/bin/kc.sh build --db=postgres --health-enabled=true --metrics-enabled=true

# The login theme and any provider JARs are added here when the theme exists (FU-0182 "custom login theme"); until then the upstream theme runs.

# Runs as the image's own non-root user (uid 1000); the platform's manifests set it explicitly too.
ENTRYPOINT ["/opt/keycloak/bin/kc.sh"]
# The default command: the optimised start. Runtime options come from KC_* environment variables.
CMD ["start", "--optimized"]
