import uuid
from decimal import Decimal
from typing import Dict, Any, Tuple
from django.db import transaction
from django.contrib.auth.models import User
from django.utils import timezone

from .models import Invoice, InvoiceItem, PaymentTransaction, CashRegisterSession
from inventory.models import DrugBatch, StockMovement
from customers.models import Customer, DueLedger
from .cart import POSCartManager


class POSCheckoutService:
    """
    Handles atomic execution of retail checkout, stock deduction (FEFO),
    financial calculations, due ledger balance updates, and invoice creation.
    """

    @classmethod
    @transaction.atomic
    def process_checkout(
        cls,
        cart_manager: POSCartManager,
        cashier: User,
        payment_method: str,
        paid_amount: Decimal,
        customer_id: str = None,
        customer_name: str = "Walk-in Customer",
        customer_phone: str = "",
        gateway_trx_id: str = "",
        doctor_name: str = "",
        register_session_id: str = None,
        tenant = None,
    ) -> Tuple[Invoice, Dict[str, Any]]:
        cart = cart_manager.get_cart_summary()
        
        if not cart["items"]:
            raise ValueError("Cannot checkout with an empty cart.")

        # POS checkout must always be attached to one tenant.
        if not tenant and hasattr(cashier, "staff_profile") and cashier.staff_profile:
            tenant = cashier.staff_profile.tenant
        if not tenant:
            raise ValueError("Select an active pharmacy before completing checkout.")

        # Generate unique invoice sequence (INV-YYYYMMDD-XXXX)
        today_str = timezone.now().strftime("%Y%m%d")
        random_suffix = uuid.uuid4().hex[:6].upper()
        invoice_number = f"INV-{today_str}-{random_suffix}"

        subtotal_mrp = Decimal(cart["subtotal_mrp"])
        discount_amount = Decimal(cart["discount_amount"])
        discount_percent = Decimal(cart["discount_percent"])
        vat_percent = Decimal(cart["vat_percent"])
        vat_amount = Decimal(cart["vat_amount"])
        total_payable = Decimal(cart["total_payable"])

        # Cash sales must be fully paid at the counter; never create an accidental due.
        if payment_method == "CASH" and paid_amount < total_payable:
            raise ValueError("Cash received is less than the amount payable.")

        # Customer Resolution
        customer = None
        if customer_id:
            cust_qs = Customer.objects.select_for_update().filter(id=customer_id)
            if tenant:
                cust_qs = cust_qs.filter(tenant=tenant)
            customer = cust_qs.first()

        # Calculate Due & Change
        if paid_amount >= total_payable:
            due_amount = Decimal("0.00")
            change_returned = paid_amount - total_payable
            actual_paid = total_payable
            status = "COMPLETED"
        else:
            due_amount = total_payable - paid_amount
            change_returned = Decimal("0.00")
            actual_paid = paid_amount
            status = "PARTIAL" if paid_amount > 0 else "PARTIAL"

            # Check customer attachment for due sales (Baki)
            if not customer and due_amount > 0:
                # Auto-create or find customer by phone if provided
                if customer_phone:
                    customer, _ = Customer.objects.get_or_create(
                        phone=customer_phone,
                        tenant=tenant,
                        defaults={"name": customer_name or "Due Customer"}
                    )
                else:
                    raise ValueError("Customer profile or phone number is required to record due (Baki).")

        # Create Invoice
        invoice = Invoice.objects.create(
            tenant=tenant,
            invoice_number=invoice_number,
            register_session_id=register_session_id,
            customer=customer,
            customer_name_walkin=customer_name or (customer.name if customer else "Walk-in Customer"),
            customer_phone_walkin=customer_phone or (customer.phone if customer else ""),
            subtotal_mrp=subtotal_mrp,
            discount_percent=discount_percent,
            discount_amount=discount_amount,
            vat_percent=vat_percent,
            vat_amount=vat_amount,
            total_payable=total_payable,
            paid_amount=actual_paid,
            due_amount=due_amount,
            change_returned=change_returned,
            payment_method=payment_method,
            status=status,
            cashier=cashier,
            doctor_name=doctor_name,
        )

        # Lock all sold batches in one query. The former per-line select_for_update
        # added one database round-trip for every medicine in the bill.
        batch_ids = [item["batch_id"] for item in cart["items"]]
        locked_batches = {
            str(batch.id): batch
            for batch in DrugBatch.objects.select_for_update()
            .filter(id__in=batch_ids, tenant=tenant)
            .select_related("drug")
        }

        # Process each line and deduct stock from its locked batch.
        for item in cart["items"]:
            batch = locked_batches.get(str(item["batch_id"]))
            if not batch:
                raise ValueError("A medicine batch in the cart is no longer available.")
            qty = int(item["quantity"])

            if batch.current_stock < qty:
                raise ValueError(
                    f"Insufficient stock for {batch.drug.brand_name} (Batch: {batch.batch_number}). "
                    f"Available: {batch.current_stock}, Requested: {qty}"
                )

            # Deduct Stock
            batch.current_stock -= qty
            batch.save(update_fields=["current_stock", "updated_at"])

            # Record Stock Movement
            StockMovement.objects.create(
                batch=batch,
                movement_type="SALE",
                quantity=-qty,
                balance_after=batch.current_stock,
                reference_id=invoice.invoice_number,
                created_by=cashier.username,
                notes=f"POS Checkout to {customer_name}"
            )

            # Create Invoice Item
            unit_mrp = Decimal(item["unit_mrp"])
            unit_tp = Decimal(item["unit_tp"])
            line_total = Decimal(item["line_total"])

            InvoiceItem.objects.create(
                invoice=invoice,
                drug=batch.drug,
                batch=batch,
                quantity=qty,
                unit_mrp=unit_mrp,
                unit_purchase_price=unit_tp,
                line_total=line_total,
                discount_amount=Decimal("0.00"),
                vat_amount=Decimal("0.00"),
            )

        # Record Payment Transaction
        if actual_paid > 0:
            PaymentTransaction.objects.create(
                invoice=invoice,
                payment_method=payment_method,
                amount=actual_paid,
                transaction_reference=gateway_trx_id or f"POS-{invoice_number}",
                received_by=cashier.username
            )

        # Update Customer Due Ledger if Due > 0
        if due_amount > 0 and customer:
            balance_before = customer.current_due
            customer.current_due += due_amount
            customer.save(update_fields=["current_due", "updated_at"])

            DueLedger.objects.create(
                tenant=tenant,
                customer=customer,
                transaction_type="INVOICE_DUE",
                amount=due_amount,
                balance_before=balance_before,
                balance_after=customer.current_due,
                invoice_reference=invoice.invoice_number,
                collected_by=cashier.username,
                notes=f"Due for Invoice #{invoice.invoice_number}"
            )

        # Clear Redis Cart
        cart_manager.clear()

        return invoice, {
            "invoice_number": invoice.invoice_number,
            "total_payable": str(total_payable),
            "paid_amount": str(actual_paid),
            "due_amount": str(due_amount),
            "change_returned": str(change_returned),
            "status": invoice.status,
            "created_at": invoice.created_at.strftime("%Y-%m-%d %I:%M %p"),
        }


class ThermalReceiptGenerator:
    """
    Generates ESC/POS byte sequence commands and clean HTML for 58mm and 80mm thermal receipt printers.
    """
    ESC = b'\x1b'
    GS = b'\x1d'
    
    @classmethod
    def generate_escpos_raw_bytes(cls, invoice: Invoice, store_name: str = "PHARMACY CARE", store_phone: str = "01700000000") -> bytes:
        """
        Produces raw ESC/POS binary buffer for direct USB/Network thermal printer streaming.
        """
        buf = bytearray()
        
        # Initialize printer
        buf.extend(cls.ESC + b'@')
        
        # Center align & Double height store name
        buf.extend(cls.ESC + b'a\x01')  # Center
        buf.extend(cls.ESC + b'!\x30')  # Double size
        buf.extend(f"{store_name}\n".encode('utf-8'))
        buf.extend(cls.ESC + b'!\x00')  # Reset font
        buf.extend(f"Tel: {store_phone}\n".encode('utf-8'))
        buf.extend(b"--------------------------------\n")
        
        # Invoice metadata (Left align)
        buf.extend(cls.ESC + b'a\x00')
        buf.extend(f"Invoice: {invoice.invoice_number}\n".encode('utf-8'))
        buf.extend(f"Date   : {invoice.created_at.strftime('%d/%m/%Y %I:%M %p')}\n".encode('utf-8'))
        buf.extend(f"Cashier: {invoice.cashier.username}\n".encode('utf-8'))
        buf.extend(f"Customer: {invoice.customer_name_walkin}\n".encode('utf-8'))
        buf.extend(b"--------------------------------\n")
        
        # Table Header
        buf.extend(b"Item             Qty  Price  Tot\n")
        buf.extend(b"--------------------------------\n")
        
        for item in invoice.items.select_related("drug", "batch"):
            name = f"{item.drug.brand_name} {item.drug.strength}"[:16].ljust(16)
            qty = str(item.quantity).rjust(3)
            price = f"{item.unit_mrp:.1f}".rjust(6)
            tot = f"{item.line_total:.1f}".rjust(5)
            buf.extend(f"{name} {qty} {price} {tot}\n".encode('utf-8'))
            
        buf.extend(b"--------------------------------\n")
        buf.extend(cls.ESC + b'a\x02')  # Right align
        buf.extend(f"Subtotal: BDT {invoice.subtotal_mrp:.2f}\n".encode('utf-8'))
        if invoice.discount_amount > 0:
            buf.extend(f"Discount: -BDT {invoice.discount_amount:.2f}\n".encode('utf-8'))
        if invoice.vat_amount > 0:
            buf.extend(f"VAT (2.4%): BDT {invoice.vat_amount:.2f}\n".encode('utf-8'))
            
        buf.extend(cls.ESC + b'!\x20')  # Bold/Enlarged
        buf.extend(f"NET TOTAL: BDT {invoice.total_payable:.2f}\n".encode('utf-8'))
        buf.extend(cls.ESC + b'!\x00')
        buf.extend(f"Paid ({invoice.payment_method}): BDT {invoice.paid_amount:.2f}\n".encode('utf-8'))
        if invoice.due_amount > 0:
            buf.extend(f"Due (Baki): BDT {invoice.due_amount:.2f}\n".encode('utf-8'))
        if invoice.change_returned > 0:
            buf.extend(f"Change: BDT {invoice.change_returned:.2f}\n".encode('utf-8'))
            
        # Footer
        buf.extend(cls.ESC + b'a\x01')  # Center
        buf.extend(b"\nThank you for choosing us!\n")
        buf.extend(b"Medicines sold without cold chain\ncan be returned within 7 days with slip.\n")
        
        # Cut paper
        buf.extend(cls.GS + b'V\x41\x00')
        return bytes(buf)

