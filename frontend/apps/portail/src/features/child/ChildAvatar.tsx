import { useTranslation } from "@mwangaza/i18n";
import { Avatar, cn, initials } from "@mwangaza/ui";

/** Photo de l'enfant si le parent y a consenti (le serveur ne donne l'adresse qu'alors), sinon
 *  ses initiales. */
export function ChildAvatar({
  name,
  photo,
  className,
}: {
  name: string;
  photo: string | null;
  className?: string;
}) {
  const { t } = useTranslation();
  if (photo) {
    return (
      <img
        src={photo}
        alt={t("portal.child.photo", { name })}
        className={cn("shrink-0 rounded-full object-cover", className)}
      />
    );
  }
  const names = name.split(" ");
  return <Avatar text={initials(names[0] ?? "", names.at(-1) ?? "")} className={className} />;
}
