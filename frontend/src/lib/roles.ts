/** 与后端 role 对齐；兼容旧值 admin。 */

export function isSudo(role?: string | null, isSudoFlag?: boolean | null): boolean {
  if (isSudoFlag) return true;
  return role === "sudo";
}

export function isSuperAdmin(role?: string | null): boolean {
  return role === "sudo" || role === "super_admin" || role === "admin";
}

export function isSubAdmin(role?: string | null): boolean {
  return role === "sub_admin";
}

export function isStaff(role?: string | null): boolean {
  return isSuperAdmin(role) || isSubAdmin(role);
}

/** sudo 视角切换用的「假装角色」 */
export type SudoViewAs = "super_admin" | "sub_admin" | "participant";
