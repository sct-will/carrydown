# Delivery modes: the planned modes and their contract stubs

Version 1 of carrydown supports embedded delivery: approved material lives in the engineering repository for everyone who can read it. The two other delivery modes below are planned. This page is the contract that version 1 formats honor so those modes can be added later without a redesign. It is reproduced from Part H of the handoff specification. For the plain-language support positions, read [the enterprise security questions](enterprise-security.md); for the technical detail, read [the security guide](security.md).

Reserving a format extension does not constitute support. Both modes are **Planned: unavailable in version 1**. Endpoint designs, authentication flows, hosting, caching and storage products are left to their future specifications. Unresolved choices are marked.

## H1. Shared constraints that version 1 must honor now

- Bundle identity and integrity depend on `content_sha256` and the content manifest, never on a repository path or a GitHub URL.
- Releases bind an exact content manifest to approval authority, audience, destinations, source versions and downstream-use permissions. Future modes add fields under `extensions`; they do not change existing ones.
- Storage location does not establish authorization. A bundle found in a store is not thereby approved for the reader.
- `bundle_format`, `receipt_format` and `format` fields are integers; readers refuse formats they do not know. `extensions` is a map keyed by mode name with its own `format` integer.
- An unsupported mode, or a required control that is missing, causes a clear refusal (`restricted-destination-unsupported`). It never falls back to embedded delivery.
- Private approval and identity metadata do not appear in the engineering repository; the receipt carries only what the verifier needs to find the evidence.

## H2. The two stubs

| Contract area | Restricted stored delivery | Brokered retrieval |
| --- | --- | --- |
| Purpose | Distribute approved bundles through a store with a narrower audience than the engineering repository. | Deliver approved context after checking authorization for each retrieval. |
| Access boundary | The store and the recipient environment enforce access. | The retrieval service and the identity system enforce access. |
| Approval | Identify the exact approved bundle, audience, destination and permitted downstream uses. | Preserve the same approval requirements, plus current retrieval authorization. |
| Freshness and withdrawal | Define permitted offline use and acknowledge that existing copies cannot be recalled. | Define current-status checks, outage behavior and withdrawal of future retrieval. Already delivered plaintext remains outside recall. |
| Evidence | Identify the release and bundle version used. Distinguish distribution records from actual read records. | Record requester, release, bundle version, authorization decision and time without logging confidential content. |
| Support status | Planned; unavailable in version 1. | Planned; unavailable in version 1. |
| Unresolved | Store type (private git repository, object store, registry); how the engineers' skill learns the store location without reading it from a tracked file; offline cache policy. | Protocol (a resource server over an open agent protocol is the leading candidate); identity integration; outage behavior; which agents can present user identity. |
