// Composants partagés de la Gestion et du Portail (skill `design`, table « Composants »).
export { Avatar, initials } from "./components/avatar";
export { Banner } from "./components/banner";
export { Brand, BrandMark, PlatformMark } from "./components/brand";
export { Button, buttonVariants } from "./components/button";
export { Card, CardContent, CardFooter, CardHeader, CardTitle, List } from "./components/card";
export { Checkbox, CheckboxField } from "./components/checkbox";
export { Code, CodeList } from "./components/code";
export { ConfirmDialog } from "./components/confirm-dialog";
export { CodeInput } from "./components/code-input";
export {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "./components/dropdown-menu";
export { Field, type FieldControlProps } from "./components/field";
export { Input, PasswordInput, Textarea, inputClasses } from "./components/input";
export { PageHeader } from "./components/page-header";
export { StatusPill, Tag } from "./components/pill";
export { SchoolBadge } from "./components/school-badge";
export { Segmented } from "./components/segmented";
export { Select } from "./components/select";
export {
  DialogClose,
  DialogContent,
  DialogRoot,
  Sheet,
  SheetClose,
  SheetContent,
  SheetTrigger,
} from "./components/sheet";
export { Skeleton } from "./components/skeleton";
export { StateCard } from "./components/state-card";
export { Steps } from "./components/steps";
export { Switch } from "./components/switch";
export { Table } from "./components/table";
export { Tabs, TabsContent, TabsList, TabsTrigger } from "./components/tabs";
export { SyncIndicator } from "./components/sync-indicator";
export { Toast } from "./components/toast";
export { Kpi } from "./components/kpi";
export {
  type DayNames,
  isoWeekday,
  type ScheduleLesson,
  toSchedule,
  WeekSchedule,
  weekdaysOf,
} from "./components/week-schedule";
export { Icon, type IconName } from "./icons";
export { cn } from "./lib/cn";
export { DESKTOP, useMediaQuery } from "./media";
export {
  applyPlatform,
  LegalNotice,
  NO_PLATFORM,
  PlatformContext,
  type PlatformIdentity,
  usePlatform,
} from "./platform";
export { createPush, type PushKeys, type PushState } from "./push";
export {
  isInstalled,
  isIos,
  listenForInstallPrompt,
  useInstallPrompt,
  useJustInstalled,
} from "./install";
