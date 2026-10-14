// Recherche `Ctrl K` de l'en-tête (M9) : élèves par noms, matricule ou code famille, comme la
// liste (côté serveur, sans accents) ; Entrée ouvre le premier trouvé. Avec `students.view`
// seulement. Reçus : avec la caisse (3.x) ; hors-ligne : 3.x.
import { useTranslation } from "@mwangaza/i18n";
import { DialogContent, DialogRoot, Icon, Input } from "@mwangaza/ui";
import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router";

import { studentName } from "../../lib/people";
import { useSettled } from "../../lib/settled";
import { useStudentSearch } from "../students/data";

const SHOWN = 8;

export function SearchPalette() {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      // Déjà pris par l'écran (caisse : sa propre recherche d'élève).
      if (event.defaultPrevented) return;
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setOpen(true);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);
  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        aria-label={t("shell.search.title")}
        className="flex min-h-11 min-w-11 items-center justify-center gap-2 rounded-field border border-line bg-surface px-3 text-ink-3 min-[900px]:max-w-[460px] min-[900px]:flex-1 min-[900px]:justify-start"
      >
        <Icon name="search" size={18} />
        <span className="hidden truncate min-[900px]:inline">{t("shell.search.open")}</span>
        <kbd className="ml-auto hidden shrink-0 whitespace-nowrap rounded-[5px] border border-b-2 border-line bg-card px-1.5 text-xs text-ink-2 min-[900px]:inline">
          {t("shell.search.shortcut")}
        </kbd>
      </button>
      <DialogRoot open={open} onOpenChange={setOpen}>
        {open && <SearchDialog onClose={() => setOpen(false)} />}
      </DialogRoot>
    </>
  );
}

function SearchDialog({ onClose }: { onClose: () => void }) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [search, setSearch] = useState("");
  const settled = useSettled(search.trim());
  const found = useStudentSearch(settled);
  const results = settled.length >= 2 ? (found.data?.results ?? []).slice(0, SHOWN) : [];
  return (
    <DialogContent title={t("shell.search.title")} className="top-[15vh] translate-y-0">
      <Input
        autoFocus
        type="search"
        aria-label={t("shell.search.label")}
        placeholder={t("shell.search.label")}
        value={search}
        onChange={(event) => setSearch(event.target.value)}
        onKeyDown={(event) => {
          const [first] = results;
          if (event.key === "Enter" && first) {
            event.preventDefault();
            onClose();
            void navigate(`/students/${first.id}`);
          }
        }}
      />
      {settled.length < 2 ? (
        <p className="text-sm text-ink-3">{t("shell.search.hint")}</p>
      ) : found.data && results.length === 0 ? (
        <p className="text-sm text-ink-3">{t("shell.search.none")}</p>
      ) : (
        <ul className="flex flex-col">
          {results.map((student) => (
            <li key={student.id}>
              <Link
                to={`/students/${student.id}`}
                onClick={onClose}
                className="flex min-h-11 flex-wrap items-center justify-between gap-2 rounded-field px-2 py-2 text-ink no-underline hover:bg-surface focus:bg-surface"
              >
                <b>{studentName(student)}</b>
                <span className="text-sm text-ink-3 tabular-nums">
                  {[student.enrollment?.class_group_name, student.matricule]
                    .filter(Boolean)
                    .join(" · ")}
                </span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </DialogContent>
  );
}
