import { createPortal } from "react-dom";
import type { ReactNode } from "react";

/** 将模态挂到 document.body，避免侧栏/入场动画祖先截断 fixed 遮罩 */
export function ModalPortal({ children }: { children: ReactNode }) {
  if (typeof document === "undefined") return null;
  return createPortal(children, document.body);
}

type OverlayProps = {
  onClose: () => void;
  children: ReactNode;
  className?: string;
};

/** 全视口遮罩 + Portal；子节点需自行 stopPropagation */
export function ModalOverlay({
  onClose,
  children,
  className = "profile-overlay",
}: OverlayProps) {
  return (
    <ModalPortal>
      <div className={className} onClick={onClose} role="presentation">
        {children}
      </div>
    </ModalPortal>
  );
}
