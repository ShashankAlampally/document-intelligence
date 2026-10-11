import type { LucideIcon } from 'lucide-react';
import { ChevronDown } from './icons';
import type { ReactNode } from 'react';

/** Native details behavior with the same icon, label and chevron alignment everywhere. */
export function DisclosureLabel({ icon: Icon, children }: { icon: LucideIcon; children: ReactNode }) {
  return <><Icon size={17} aria-hidden="true"/><span className="disclosure-label">{children}</span><ChevronDown size={16} className="disclosure-chevron" aria-hidden="true"/></>;
}
