// Salles et ateliers (EDT.1a, maquette `salles`) : les lieux où se donnent les cours, avec leur
// type et leurs places. Une salle n'est jamais supprimée : on la retire (l'horaire s'y réfère).
import { api, call } from "@mwangaza/api";
import { useTranslation } from "@mwangaza/i18n";
import {
  Banner,
  Button,
  Card,
  CardContent,
  DialogClose,
  DialogContent,
  DialogRoot,
  Field,
  Input,
  PageHeader,
  Segmented,
  Select,
  Skeleton,
  StatusPill,
  Table,
} from "@mwangaza/ui";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router";

import { firstErrorMessage } from "../../lib/errors";
import { keys } from "../../lib/queries";
import { LoadError } from "../status/StatusPages";
import { ROOM_KINDS, useRooms, type Room, type RoomKind } from "./data";

type Filter = "all" | "classroom" | "workshop" | "other";
type Draft = { id: string | null; name: string; kind: RoomKind; capacity: string };

const filterOf = (kind: RoomKind): Filter =>
  kind === "classroom" || kind === "workshop" ? kind : "other";

export function RoomsPage() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const rooms = useRooms();
  const [filter, setFilter] = useState<Filter>("all");
  const [draft, setDraft] = useState<Draft | null>(null);
  const refresh = () => void queryClient.invalidateQueries({ queryKey: keys.timetable });

  const save = useMutation({
    mutationFn: (input: Draft) => {
      const body = {
        name: input.name.trim(),
        kind: input.kind,
        capacity: input.capacity ? Number(input.capacity) : null,
      };
      return input.id
        ? call(
            api.PATCH("/api/timetable/rooms/{id}/", { params: { path: { id: input.id } }, body }),
          )
        : call(api.POST("/api/timetable/rooms/", { body }));
    },
    onSuccess: () => {
      setDraft(null);
      refresh();
    },
  });
  const toggle = useMutation({
    mutationFn: (room: Room) =>
      call(
        api.PATCH("/api/timetable/rooms/{id}/", {
          params: { path: { id: room.id } },
          body: { is_active: !room.is_active },
        }),
      ),
    onSuccess: refresh,
  });

  if (rooms.isPending) return <Skeleton label={t("common.loading")} />;
  if (rooms.isError) return <LoadError error={rooms.error} onRetry={() => void rooms.refetch()} />;

  const count = (value: Filter) =>
    value === "all"
      ? rooms.data.length
      : rooms.data.filter((room) => filterOf(room.kind) === value).length;
  const shown = rooms.data.filter((room) => filter === "all" || filterOf(room.kind) === filter);
  const filters: Filter[] = ["all", "classroom", "workshop", "other"];

  return (
    <>
      <PageHeader
        title={t("timetable.roomsTitle")}
        subtitle={t("timetable.roomsSubtitle")}
        actions={
          <>
            <Button asChild variant="outline">
              <Link to="/time-grid">{t("timetable.gridLink")}</Link>
            </Button>
            <Button
              onClick={() => setDraft({ id: null, name: "", kind: "classroom", capacity: "" })}
            >
              {t("timetable.addRoom")}
            </Button>
          </>
        }
      />
      <div className="mb-4 max-w-full overflow-x-auto">
        <Segmented
          className="w-max"
          label={t("timetable.roomFilter")}
          value={filter}
          onValueChange={setFilter}
          options={filters.map((value) => ({
            value,
            label: t("timetable.filterCount", {
              label: t(`timetable.filters.${value}`),
              total: count(value),
            }),
          }))}
        />
      </div>
      <Card>
        <CardContent className="flex flex-col gap-4 pt-6">
          {shown.length === 0 ? (
            <p className="text-ink-3">{t("timetable.roomsEmpty")}</p>
          ) : (
            <Table stacked>
              <thead>
                <tr>
                  <th>{t("timetable.room")}</th>
                  <th>{t("timetable.kind")}</th>
                  <th className="text-right">{t("timetable.capacity")}</th>
                  <th>{t("timetable.roomClasses")}</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {shown.map((room) => (
                  <tr key={room.id} className={room.is_active ? "" : "opacity-60"}>
                    <td data-label={t("timetable.room")} data-wrap className="font-semibold">
                      {room.name}
                      {!room.is_active && (
                        <StatusPill tone="warn" className="ml-2">
                          {t("timetable.retired")}
                        </StatusPill>
                      )}
                    </td>
                    <td data-label={t("timetable.kind")}>{t(`timetable.kinds.${room.kind}`)}</td>
                    <td data-label={t("timetable.capacity")} className="text-right tabular-nums">
                      {room.capacity ?? "—"}
                    </td>
                    <td data-label={t("timetable.roomClasses")} data-wrap>
                      {room.classes.length > 0 ? room.classes.join(", ") : "—"}
                    </td>
                    <td>
                      <div className="flex justify-end gap-2">
                        {room.is_active && (
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() =>
                              setDraft({
                                id: room.id,
                                name: room.name,
                                kind: room.kind,
                                capacity: room.capacity ? String(room.capacity) : "",
                              })
                            }
                          >
                            {t("timetable.edit")}
                          </Button>
                        )}
                        <Button
                          size="sm"
                          variant="outline"
                          disabled={toggle.isPending}
                          onClick={() => toggle.mutate(room)}
                        >
                          {room.is_active ? t("timetable.retire") : t("timetable.restore")}
                        </Button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </Table>
          )}
          {toggle.isError && <Banner tone="due">{firstErrorMessage(toggle.error, t)}</Banner>}
          <p className="text-sm text-ink-3">{t("timetable.roomsHelp")}</p>
        </CardContent>
      </Card>
      <DialogRoot open={draft !== null} onOpenChange={(open) => !open && setDraft(null)}>
        {draft && (
          <DialogContent
            title={draft.id ? t("timetable.editRoomTitle") : t("timetable.addRoom")}
            footer={
              <>
                <DialogClose asChild>
                  <Button variant="outline">{t("common.cancel")}</Button>
                </DialogClose>
                <Button
                  disabled={save.isPending || draft.name.trim() === ""}
                  onClick={() => save.mutate(draft)}
                >
                  {t("timetable.saveRoom")}
                </Button>
              </>
            }
          >
            <div className="flex flex-col gap-4">
              <Field id="room-name" label={t("timetable.name")} required>
                {(control) => (
                  <Input
                    {...control}
                    maxLength={80}
                    value={draft.name}
                    onChange={(event) => setDraft({ ...draft, name: event.target.value })}
                  />
                )}
              </Field>
              <Field id="room-kind" label={t("timetable.kind")}>
                {(control) => (
                  <Select
                    {...control}
                    value={draft.kind}
                    onChange={(event) =>
                      setDraft({ ...draft, kind: event.target.value as RoomKind })
                    }
                  >
                    {ROOM_KINDS.map((kind) => (
                      <option key={kind} value={kind}>
                        {t(`timetable.kinds.${kind}`)}
                      </option>
                    ))}
                  </Select>
                )}
              </Field>
              <Field id="room-capacity" label={t("timetable.capacityOptional")}>
                {(control) => (
                  <Input
                    {...control}
                    type="number"
                    min={1}
                    max={500}
                    inputMode="numeric"
                    value={draft.capacity}
                    onChange={(event) => setDraft({ ...draft, capacity: event.target.value })}
                  />
                )}
              </Field>
              <p className="text-sm text-ink-3">{t("timetable.kindHelp")}</p>
              {save.isError && <Banner tone="due">{firstErrorMessage(save.error, t)}</Banner>}
            </div>
          </DialogContent>
        )}
      </DialogRoot>
    </>
  );
}
