type FaithPanelProps = {
  children: React.ReactNode;
  className?: string;
};

export default function FaithPanel({ children, className = "" }: FaithPanelProps) {
  return <div className={`faith-frame ${className}`}>{children}</div>;
}
