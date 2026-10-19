---
type: service
id: svc_auth
name: auth-service
aliases: [auth service, authentication service]
owner_team: Platform Team
owner: Alex Chen
depends_on: [ledger-db]
uses: [Vault]
tier: 0
author: Alex Chen
updated: 2026-08-30
---

# auth-service

## Summary

auth-service issues and validates OAuth2 access tokens for internal services and external partners, and validates legacy API keys for v2 customers. Signing keys and API key secrets are stored in HashiCorp Vault.

## Ownership

The Platform Team owns auth-service and Alex Chen is the primary owner. James Owusu from Security & Compliance reviews every change to token lifetimes and signing algorithms.

## Security controls

1. Internal calls use mutual TLS, following ADR-007.
2. API key secrets rotate every 30 days, following ADR-009.
3. Partner tokens use the OAuth2 client credentials grant, following ADR-008.

## Known issues

ArgoCD sync for auth-service fails intermittently on the new Triton clusters because of a CRD ordering problem (TRI-19).
