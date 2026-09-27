const reply = (body, status = 200) => new Response(JSON.stringify(body), {
  status, headers: {'Content-Type':'application/json','Cache-Control':'no-store'}
});
const validDescription = (value, type) => value && value.type === type &&
  typeof value.sdp === 'string' && value.sdp.startsWith('v=0') && value.sdp.length <= 65536;

// Only negotiation metadata lives here; camera video travels over encrypted WebRTC.
export async function cameraSignaling(request, db, user, session, bodyOf) {
  const path = new URL(request.url).pathname;
  const now = Date.now();
  if (path === '/camera/rooms' && request.method === 'POST') {
    const body = await bodyOf(request);
    if (!validDescription(body.offer, 'offer')) return reply({error:'Invalid camera offer.'},400);
    const code = Array.from(crypto.getRandomValues(new Uint8Array(6)), b=>b.toString(16).padStart(2,'0')).join('').toUpperCase();
    await db.batch([
      db.prepare('DELETE FROM camera_rooms WHERE expires_at<=? OR owner_id=?').bind(now,user.id),
      db.prepare('INSERT INTO camera_rooms(code,owner_session,owner_id,offer,expires_at) VALUES(?,?,?,?,?)')
        .bind(code,session,user.id,JSON.stringify(body.offer),now+600000)
    ]);
    return reply({code,expires_at:now+600000},201);
  }
  const match = path.match(/^\/camera\/rooms\/([A-F0-9]{12})(?:\/(join|approve|answer|close))?$/);
  if (!match) return reply({error:'Camera link not found.'},404);
  const [,code,action] = match;
  const room = await db.prepare('SELECT * FROM camera_rooms WHERE code=? AND expires_at>?').bind(code,now).first();
  if (!room) return reply({error:'This camera code expired. Start a new camera link.'},404);
  const owner = room.owner_session === session;
  const receiver = room.receiver_session === session;
  if (action === 'join' && request.method === 'POST') {
    if (owner) return reply({error:'Open the receiving page on a different device or browser session.'},409);
    const joined = await db.prepare(`UPDATE camera_rooms SET receiver_session=?,receiver_name=?
      WHERE code=? AND expires_at>? AND (receiver_session IS NULL OR receiver_session=?) RETURNING code`)
      .bind(session,user.display_name,code,now,session).first();
    return joined ? reply({waiting:true}) : reply({error:'Another device is already using this code.'},409);
  }
  if (!owner && !receiver) return reply({error:'This camera link belongs to another device.'},403);
  if (request.method === 'GET' && !action) {
    return reply(owner ? {receiver_name:room.receiver_name,approved:!!room.approved,answer:room.answer?JSON.parse(room.answer):null}
      : {approved:!!room.approved,offer:room.approved?JSON.parse(room.offer):null});
  }
  if (request.method === 'POST' && action === 'approve' && owner && room.receiver_session) {
    await db.prepare('UPDATE camera_rooms SET approved=1 WHERE code=?').bind(code).run();
    return reply({ok:true});
  }
  if (request.method === 'POST' && action === 'answer' && receiver && room.approved) {
    const body=await bodyOf(request);
    if (!validDescription(body.answer,'answer')) return reply({error:'Invalid camera answer.'},400);
    // A retry may repeat the same answer; it cannot replace a negotiated connection.
    const answer=JSON.stringify(body.answer);
    const updated=await db.prepare('UPDATE camera_rooms SET answer=? WHERE code=? AND (answer IS NULL OR answer=?) RETURNING code')
      .bind(answer,code,answer).first();
    return updated ? reply({ok:true}) : reply({error:'This connection has already been answered.'},409);
  }
  if (request.method === 'POST' && action === 'close') {
    await db.prepare('DELETE FROM camera_rooms WHERE code=?').bind(code).run();
    return reply({ok:true});
  }
  return reply({error:'This camera action is not allowed.'},403);
}
