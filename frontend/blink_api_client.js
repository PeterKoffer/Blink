/* Blink API client — drop-in JS for the single-file prototype.
 *
 * Usage (inside kidschat_demo.py's embedded <script>):
 *
 *   <script src="/static/blink_api_client.js"></script>   // or inline
 *   const api = new BlinkAPI({
 *     baseUrl: "http://localhost:8000",      // wherever the FastAPI app runs
 *     devUserId: "sofies-user-uuid",          // only works with BLINK_DEV_BYPASS_AUTH=true
 *   });
 *
 *   // Calls return parsed JSON on 2xx. On non-2xx, throw a BlinkAPIError
 *   // that carries the typed error body so the UI can render precise states
 *   // (upgrade_required, hard_cap_exceeded, rate_limited, ...).
 *
 *   try {
 *     const groups = await api.groups.list();
 *   } catch (e) {
 *     if (e.code === "upgrade_required") { ... showUpgradeCta(e.details.requiredTier) ... }
 *   }
 *
 * All names here match the master spec's camelCase wire format.
 */

(function (global) {
  "use strict";

  class BlinkAPIError extends Error {
    constructor(status, body) {
      const err = (body && body.error) || {};
      super(err.message || `HTTP ${status}`);
      this.status = status;
      this.code = err.code || "unknown";
      this.details = err;  // full error object from server (policyKey, requiredTier, retryAfterSeconds, ...)
    }
  }

  class BlinkAPI {
    constructor({ baseUrl, devUserId = null, jwt = null } = {}) {
      if (!baseUrl) throw new Error("baseUrl required");
      this.baseUrl = baseUrl.replace(/\/$/, "");
      this.devUserId = devUserId;
      this.jwt = jwt;

      // Scoped helper bundles so call sites read naturally.
      this.friends = {
        createRequest: (body) => this._post("/friends/requests", body),
        list: () => this._get("/friends"),
      };
      this.groups = {
        list: () => this._get("/groups"),
        get: (id) => this._get(`/groups/${id}`),
        create: (body) => this._post("/groups", body),
        join: (body) => this._post("/groups/join", body),
        invite: (id, body) => this._post(`/groups/${id}/invite`, body),
        listMessages: (id, { limit = 50, before = null } = {}) => {
          const qs = new URLSearchParams({ limit: String(limit) });
          if (before) qs.set("before", before);
          return this._get(`/groups/${id}/messages?${qs}`);
        },
      };
      this.messages = {
        createText: ({ groupId, text, clientMessageId, ttlSeconds = 60 }) =>
          this._post("/messages", {
            groupId,
            type: "text",
            text,
            clientMessageId,
            ephemeralMode: "timer",
            ttlSeconds,
          }),
        createImage: ({ groupId, mediaId, clientMessageId, ttlSeconds = 60 }) =>
          this._post("/messages", {
            groupId,
            type: "image",
            mediaId,
            clientMessageId,
            ephemeralMode: "timer",
            ttlSeconds,
          }),
      };
      this.media = {
        getUploadUrl: (body) => this._post("/media/upload-url", body),
        confirm: (mediaId) => this._post("/media/confirm", { mediaId }),
        getReadUrl: (mediaId) => this._get(`/media/${mediaId}/url`),
      };
      this.parent = {
        pending: () => this._get("/parent/requests/pending"),
        approveFriend: (id) => this._post(`/parent/requests/friend/${id}/approve`),
        declineFriend: (id) => this._post(`/parent/requests/friend/${id}/decline`),
        approveGroup: (id) => this._post(`/parent/requests/group/${id}/approve`),
        declineGroup: (id) => this._post(`/parent/requests/group/${id}/decline`),
        billing: (gid) => this._get(`/parent/groups/${gid}/billing`),
        activate: (gid, tier) => this._post(`/parent/groups/${gid}/activate`, { tier }),
        upgrade: (gid, tier) => this._post(`/parent/groups/${gid}/upgrade`, { tier }),
      };
      this.onboarding = {
        createChildProfile: ({ displayName, avatarType, avatarValue, avatarColor }) =>
          this._post("/onboarding/child-profile", {
            displayName, avatarType, avatarValue, avatarColor,
          }),
        startParentInvite: ({ childUserId, contact }) =>
          this._post("/onboarding/parent-invite", { childUserId, contact }),
        previewInvite: (token) => this._get(`/onboarding/parent-invite/${token}`),
        verifyParent: ({ inviteToken, otp }) =>
          this._post("/onboarding/parent-verify", { inviteToken, otp }),
        approveChild: ({ inviteToken, consentAccepted, consentVersion }) =>
          this._post("/onboarding/parent-approve", {
            inviteToken, consentAccepted, consentVersion,
          }),
        declineChild: ({ inviteToken }) =>
          this._post("/onboarding/parent-decline", { inviteToken }),
      };
      this.me = () => this._get("/me");
      this.media.upload = async ({ file, groupId, mime, width, height }) => {
        // 4-step image upload — see project_blink_media.md.
        const { mediaId, uploadUrl, headers } = await this.media.getUploadUrl({
          groupId, mime, size: file.size, width, height,
        });
        const putRes = await fetch(uploadUrl, {
          method: "PUT",
          body: file,
          headers,
        });
        if (!putRes.ok) {
          throw new BlinkAPIError(putRes.status, {
            error: { code: "storage_upload_failed", message: "PUT to R2 failed" },
          });
        }
        await this.media.confirm(mediaId);
        return { mediaId };
      };
    }

    _authHeaders() {
      const h = { "Content-Type": "application/json" };
      if (this.jwt) h["Authorization"] = `Bearer ${this.jwt}`;
      if (this.devUserId) h["X-Dev-User-Id"] = this.devUserId;
      return h;
    }

    async _request(method, path, body) {
      const res = await fetch(this.baseUrl + path, {
        method,
        headers: this._authHeaders(),
        body: body === undefined ? undefined : JSON.stringify(body),
      });
      let parsed = null;
      try { parsed = await res.json(); } catch { /* empty body */ }
      if (!res.ok) {
        throw new BlinkAPIError(res.status, parsed);
      }
      return parsed;
    }

    _get(path) { return this._request("GET", path); }
    _post(path, body) { return this._request("POST", path, body || {}); }
  }

  global.BlinkAPI = BlinkAPI;
  global.BlinkAPIError = BlinkAPIError;
})(typeof window !== "undefined" ? window : globalThis);
