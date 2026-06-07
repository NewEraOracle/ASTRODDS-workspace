import FaithPanel from "./FaithPanel";

type FaithModuleCardProps = {
  title: string;
  body: string;
  image: string;
};

export default function FaithModuleCard({ title, body, image }: FaithModuleCardProps) {
  return (
    <FaithPanel className="group overflow-hidden p-5 transition hover:border-cyan-100/50">
      <div className="flex items-center gap-5">
        <div className="asset-shell grid h-24 w-24 shrink-0 place-items-center border border-cyan-100/25 bg-black/50 shadow-[0_0_30px_rgba(125,211,252,.22)]">
          <img
            src={image}
            alt={title}
            className="h-20 w-20 object-contain drop-shadow-[0_0_22px_rgba(125,211,252,.55)] transition duration-300 group-hover:scale-110"
          />
        </div>

        <div>
          <h3 className="text-sm font-black uppercase tracking-[0.28em] text-white">
            {title}
          </h3>
          <p className="mt-3 text-sm leading-6 text-slate-400">
            {body}
          </p>
          <p className="mt-4 text-[10px] font-black uppercase tracking-[0.25em] text-cyan-300">
            Learn More
          </p>
        </div>
      </div>
    </FaithPanel>
  );
}
