import { pool } from "../utils/db";

export interface BankAccount {
  id: string;
  firstName: string;
  lastName: string;
  mobileNumber: string;
  accountNumber: string;
  bankId: string;
  bankName: string;
  balance: number;
}

export async function findBankAccountsByMobile(mobileNumber: string): Promise<BankAccount[]> {
  const r = await pool.query(
    `select 
        ba.id::text, 
        ba.first_name as "firstName",
        ba.last_name as "lastName",
        ba.mobile_number as "mobileNumber", 
        ba.account_number as "accountNumber", 
        ba.bank_id::text as "bankId", 
        b.name as "bankName", 
        ba.balance::float as balance
     from bank_accounts ba
     join banks b on b.id = ba.bank_id
     where ba.mobile_number = $1`,
    [mobileNumber]
  );
  return r.rows;
}

export async function getBankAccountById(id: string): Promise<BankAccount | null> {
  const r = await pool.query(
    `select 
        ba.id::text, 
        ba.first_name as "firstName",
        ba.last_name as "lastName",
        ba.mobile_number as "mobileNumber", 
        ba.account_number as "accountNumber", 
        ba.bank_id::text as "bankId", 
        b.name as "bankName", 
        ba.balance::float as balance
     from bank_accounts ba
     join banks b on b.id = ba.bank_id
     where ba.id = $1`,
    [id]
  );
  return r.rows[0] || null;
}

export async function createBankAccount(args: {
  firstName: string;
  lastName: string;
  aadharNumber: string;
  mobileNumber: string;
  accountNumber: string;
  bankId: string;
  ifscCode: string;
  balance: number;
}) {
  const result = await pool.query(
    `insert into bank_accounts (first_name, last_name, aadhar_number, mobile_number, account_number, bank_id, ifsc_code, balance)
     values ($1, $2, $3, $4, $5, $6, $7, $8)
     returning id::text as id`,
    [
      args.firstName,
      args.lastName,
      args.aadharNumber,
      args.mobileNumber,
      args.accountNumber,
      args.bankId,
      args.ifscCode,
      args.balance
    ]
  );
  return result.rows[0];
}

export async function getAllBanks() {
  const result = await pool.query("select id::text, name from banks");
  return result.rows;
}
