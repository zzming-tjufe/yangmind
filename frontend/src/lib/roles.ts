/** 与后端 role 对齐；兼容旧值 admin。 */

export function isSuperAdmin(role?: string | null): boolean {
  return role === "super_admin" || role === "admin";
}

export function isSubAdmin(role?: string | null): boolean {
  return role === "sub_admin";
}

export function isStaff(role?: string | null): boolean {
  return isSuperAdmin(role) || isSubAdmin(role);
}
