export const MATCH_SELECT = `SELECT m.*, COALESCE((SELECT hidden FROM match_privacy WHERE match_id=m.id),0) AS hidden, creator.display_name AS creator_name, editor.display_name AS editor_name
 FROM matches m LEFT JOIN users creator ON creator.id=m.owner_id LEFT JOIN users editor ON editor.id=m.updated_by`;

export function matchRecord(row) {
  const body=JSON.parse(row.body);
  return {...row, deleted:!!row.deleted, body:{...body,
    created_by_id:body.created_by_id || row.owner_id || '',
    created_by_name:body.created_by_name || row.creator_name || 'Not recorded',
    edited_by_id:body.edited_by_id || row.updated_by || '',
    edited_by_name:body.edited_by_name || row.editor_name || 'Not recorded'}};
}
