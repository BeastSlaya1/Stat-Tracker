import {cameraLinks} from './camera-links.mjs';
import {cameraSignaling} from './camera-signaling.mjs';
const encoder = new TextEncoder();
const json = (body, status = 200) => new Response(JSON.stringify(body), {
  status, headers: {"Content-Type": "application/json", "Cache-Control": "no-store"}
});
const hex = bytes => Array.from(new Uint8Array(bytes), b => b.toString(16).padStart(2, "0")).join("");
const unhex = value => Uint8Array.from(value.match(/../g), b => parseInt(b, 16));
const random = () => hex(crypto.getRandomValues(new Uint8Array(32)));
async function digest(value) { return hex(await crypto.subtle.digest("SHA-256", encoder.encode(value))); }
async function passwordHash(password, salt) {
  const key = await crypto.subtle.importKey("raw", encoder.encode(password), "PBKDF2", false, ["deriveBits"]);
  return hex(await crypto.subtle.deriveBits({name: "PBKDF2", salt: unhex(salt), iterations: 100000, hash: "SHA-256"}, key, 256));
}
function equal(a, b) {
  if (a.length !== b.length) return false;
  let result = 0;
  for (let i = 0; i < a.length; i++) result |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return result === 0;
}
async function bodyOf(request) {
  if (Number(request.headers.get("Content-Length")) > 1048576) throw new Error("too-large");
  const text = await request.text();
  if (encoder.encode(text).length > 1048576) throw new Error("too-large");
  try { return JSON.parse(text); } catch { throw new Error("invalid-json"); }
}
async function staff(request, db) {
  const authorization = request.headers.get("Authorization") || "";
  if (!authorization.startsWith("Bearer ")) return null;
  return db.prepare(`SELECT u.id, u.email, u.display_name FROM sessions s
    JOIN users u ON u.id=s.user_id WHERE s.token_hash=? AND s.expires_at>? AND u.enabled=1`)
    .bind(await digest(authorization.slice(7)), Date.now()).first();
}
function cleanEmail(value) { return typeof value === "string" ? value.trim().toLowerCase() : ""; }
function validMatch(body) {
  const object = value => !!value && typeof value === "object" && !Array.isArray(value);
  const strings = (value, keys) => object(value) && keys.every(key => typeof value[key] === "string");
  if (!strings(body, ["id","sport","title","date","location"]) || !Array.isArray(body.events)) return false;
  for (const key of ["home_team","away_team"]) {
    const team = body[key];
    if (!strings(team, ["id","name","short_name","logo_color","secondary_color","badge_symbol"])) return false;
    if (team.players !== undefined && (!Array.isArray(team.players) || team.players.some(player =>
      !strings(player,["id","name","position"]) || !Number.isFinite(player.number)))) return false;
  }
  if (body.stats !== undefined && (!object(body.stats) || Object.values(body.stats).some(value => !Number.isFinite(value)))) return false;
  return body.events.every(event => strings(event,["id","timestamp","team_id","event_type","player_name","description"])
    && Number.isFinite(event.minute));
}
async function handle(request, env) {
  const route = new URL(request.url).pathname.replace(/\/$/, '');
  if (request.method === 'GET' && route === '/camera') return Response.redirect('https://stattrackerv4.stream',302);
  if (request.method === 'GET' && route === '/camera/app.js') return json({error:'Use Camera Mode in the main app.'},410);
  const db = env.DB;
  const url = new URL(request.url);
  const path = url.pathname.replace(/\/$/, "");
  if (request.method === "GET" && path === "/health") return json({ok: true});
  if (request.method === "POST" && path === "/admin/users") {
    const supplied = (request.headers.get("Authorization") || "").replace(/^Bearer /, "");
    if (!env.ADMIN_SETUP_KEY || !equal(await digest(supplied), await digest(env.ADMIN_SETUP_KEY))) {
      return json({error: "Administrator authorization required."}, 401);
    }
    const body = await bodyOf(request);
    const email = cleanEmail(body.email);
    if (!email.includes("@") || email.length > 254 || typeof body.password !== "string" ||
        body.password.length < 12 || body.password.length > 128 ||
        typeof body.display_name !== "string" || !body.display_name.trim() || body.display_name.length > 100) {
      return json({error: "Provide an email, name, and password of 12–128 characters."}, 400);
    }
    const id = crypto.randomUUID(), salt = random();
    const result = await db.prepare(`INSERT INTO users
      (id,email,display_name,password_salt,password_hash,created_at) VALUES (?,?,?,?,?,?)
      ON CONFLICT(email) DO NOTHING RETURNING id`)
      .bind(id,email,body.display_name.trim(),salt,await passwordHash(body.password,salt),Date.now()).first();
    return result ? json({id, email}, 201) : json({error: "That staff account already exists."}, 409);
  }
  if (request.method === "POST" && path === "/login") {
    const body = await bodyOf(request);
    const email = cleanEmail(body.email);
    if (!email || email.length > 254 || typeof body.password !== "string" || body.password.length > 128) {
      return json({error: "Email or password is incorrect."}, 401);
    }
    const attemptKey = await digest((request.headers.get("CF-Connecting-IP") || "unknown") + ":" + email);
    const now = Date.now();
    const attempt = await db.prepare(`INSERT INTO login_attempts(key,count,reset_at) VALUES (?,1,?)
      ON CONFLICT(key) DO UPDATE SET count=CASE WHEN reset_at<=? THEN 1 ELSE count+1 END,
      reset_at=CASE WHEN reset_at<=? THEN excluded.reset_at ELSE reset_at END RETURNING count`)
      .bind(attemptKey, now + 600000, now, now).first();
    if (attempt.count > 10) return json({error: "Too many attempts. Try again in ten minutes."}, 429);
    const user = await db.prepare("SELECT * FROM users WHERE email=? AND enabled=1").bind(email).first();
    const computed = await passwordHash(body.password, user?.password_salt || "00".repeat(32));
    if (!user || !equal(computed, user.password_hash)) return json({error: "Email or password is incorrect."}, 401);
    const token = random(), expiresAt = now + 7 * 86400000;
    await db.batch([
      db.prepare("DELETE FROM login_attempts WHERE key=?").bind(attemptKey),
      db.prepare("DELETE FROM sessions WHERE expires_at<=?").bind(now),
      db.prepare("INSERT INTO sessions(token_hash,user_id,expires_at) VALUES (?,?,?)")
        .bind(await digest(token), user.id, expiresAt)
    ]);
    return json({token, expires_at: expiresAt, user: {id: user.id, email, display_name: user.display_name}});
  }
  const user = await staff(request, db);
  if (!user) return json({error: "Sign in to sync the shared database."}, 401);
  if (path.startsWith('/camera/devices')) return cameraLinks(request,db,user,await digest(request.headers.get('Authorization').slice(7)),bodyOf);
  if (path.startsWith('/camera/rooms')) {
    return cameraSignaling(request, db, user, await digest(request.headers.get('Authorization').slice(7)), bodyOf);
  }
  if (request.method === "POST" && path === "/logout") {
    await db.prepare("DELETE FROM sessions WHERE token_hash=?")
      .bind(await digest(request.headers.get("Authorization").slice(7))).run();
    return json({ok: true});
  }
  if (request.method === "GET" && path === "/catalog") {
    const result = await db.prepare("SELECT table_name,rows_json FROM catalog").all();
    return json(Object.fromEntries(result.results.map(row => [row.table_name, JSON.parse(row.rows_json)])));
  }
  if (request.method === "GET" && path === "/matches") {
    const after = url.searchParams.get("after") || "";
    const result = await db.prepare("SELECT * FROM matches WHERE id>? ORDER BY id LIMIT 100").bind(after).all();
    const records = result.results.map(row => ({...row, body: JSON.parse(row.body), deleted: !!row.deleted}));
    return json({records, next: records.length === 100 ? records.at(-1).id : null});
  }
  if (request.method === "PUT" && path.startsWith("/matches/")) {
    const id = decodeURIComponent(path.slice("/matches/".length));
    const body = await bodyOf(request);
    if (!/^[A-Za-z0-9_-]{1,100}$/.test(id) || !Number.isInteger(body.base_version) || body.base_version < 0 ||
        typeof body.mutation_id !== "string" || !/^[A-Za-z0-9_-]{16,100}$/.test(body.mutation_id) ||
        typeof body.deleted !== "boolean" || !validMatch(body.body) || body.body.id !== id) {
      return json({error: "Invalid match update."}, 400);
    }
    const existing = await db.prepare("SELECT * FROM matches WHERE id=?").bind(id).first();
    if (existing?.mutation_id === body.mutation_id) return json({version: existing.version});
    const values = [JSON.stringify(body.body), body.deleted ? 1 : 0, body.mutation_id, user.id, Date.now()];
    const updated = body.base_version === 0
      ? await db.prepare(`INSERT INTO matches (id,body,deleted,mutation_id,updated_by,updated_at)
          VALUES (?,?,?,?,?,?) ON CONFLICT(id) DO NOTHING RETURNING version`).bind(id,...values).first()
      : await db.prepare(`UPDATE matches SET body=?,deleted=?,mutation_id=?,updated_by=?,updated_at=?,version=version+1
          WHERE id=? AND version=? RETURNING version`).bind(...values,id,body.base_version).first();
    if (!updated) {
      const current = await db.prepare("SELECT * FROM matches WHERE id=?").bind(id).first();
      return json({error: "This match changed on another device.", current: current ? {
        ...current, body: JSON.parse(current.body), deleted: !!current.deleted} : null}, 409);
    }
    return json({version: updated.version});
  }
  return json({error: "Not found."}, 404);
}

export default {
  async fetch(request, env) {
    const origin = request.headers.get("Origin");
    const allowed = (env.ALLOWED_ORIGINS || "https://stattrackerv4.stream").split(",").map(x => x.trim());
    allowed.push(new URL(request.url).origin);
    if (origin && !allowed.includes(origin)) return json({error: "Origin not allowed."}, 403);
    let response;
    try {
      response = request.method === "OPTIONS" ? new Response(null, {status: 204}) : await handle(request, env);
    } catch (error) {
      response = error.message === "too-large" ? json({error: "Match is too large to sync."}, 413)
        : error.message === "invalid-json" ? json({error: "Invalid JSON."}, 400)
        : json({error: "Sync service temporarily unavailable."}, 503);
    }
    const headers = new Headers(response.headers);
    if (origin) headers.set("Access-Control-Allow-Origin", origin);
    headers.set("Vary", "Origin");
    headers.set("Access-Control-Allow-Headers", "Authorization, Content-Type, X-Camera-Device");
    headers.set("Access-Control-Allow-Methods", "GET, POST, PUT, OPTIONS");
    headers.set("X-Content-Type-Options", "nosniff");
    return new Response(response.body, {status: response.status, headers});
  }
};
