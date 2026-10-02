// Données fictives communes aux tests d'écrans du Portail.

export const ACCOUNT = { id: "01", phone: "+243971234567", name: "Kahindo Neema", language: "fr" };

export const currency = (code: string, total: number, paid: number, overdue: number) => ({
  currency: code,
  total_minor: total,
  paid_minor: paid,
  remaining_minor: total - paid,
  overdue_minor: overdue,
  next_due_minor: 0,
});

export const ITIG = {
  id: "f1",
  school_name: "ITIG Don Bosco Goma",
  school_timezone: "Africa/Lubumbashi",
  status: "active",
  children: [
    {
      id: "s1",
      full_name: "KASEREKA Muhindo Jean",
      class_name: "3e Électricité A",
      balance: {
        situation: "partial",
        next_due_on: "2027-01-15",
        currencies: [currency("USD", 36000, 5000, 7000), currency("CDF", 25000, 0, 25000)],
      },
      first_overdue: "Fonctionnement",
      photo: null,
      last_payment: {
        paid_at: "2026-10-08T08:42:00Z",
        received_amount_minor: 5000,
        received_currency: "USD",
      },
    },
  ],
};
