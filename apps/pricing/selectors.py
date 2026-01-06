"""
Pricing selector functions.
Resolves item pricing based on party price lists, company defaults, and fallbacks.
"""
from decimal import Decimal
from django.core.exceptions import ValidationError
from apps.inventory.models import StockItem
from apps.party.models import Party


def resolve_price(company, item, party=None):
    """
    Resolve the correct price for an item based on pricing hierarchy.
    
    Priority:
    1. Party-specific price list
    2. Company default price list
    3. Item default price
    
    Args:
        company: Company instance
        item: StockItem instance or ID
        party: Party instance (optional)
    
    Returns:
        Decimal: The resolved price
    
    Raises:
        ValidationError: If no price is available
    """
    # Get StockItem instance if ID provided
    if not isinstance(item, StockItem):
        item = StockItem.objects.get(id=item, company=company)
    
    # 1. Try party price list
    if party and hasattr(party, 'price_list') and party.price_list:
        from apps.products.models import ItemPrice
        party_price = ItemPrice.objects.filter(
            item=item,
            price_list=party.price_list
        ).order_by('-valid_from').first()
        
        if party_price:
            return party_price.rate
    
    # 2. Try company default price list
    try:
        from apps.company.models import CompanyFeature
        company_feature = CompanyFeature.objects.filter(company=company).first()
        
        if company_feature and hasattr(company_feature, 'default_price_list') and company_feature.default_price_list:
            from apps.products.models import ItemPrice
            company_price = ItemPrice.objects.filter(
                item=item,
                price_list=company_feature.default_price_list
            ).order_by('-valid_from').first()
            
            if company_price:
                return company_price.rate
    except:
        pass  # CompanyFeature or default_price_list may not exist
    
    # 3. Try item default price (most recent)
    from apps.products.models import ItemPrice
    default_price = ItemPrice.objects.filter(
        item=item
    ).order_by('-valid_from').first()
    
    if default_price:
        return default_price.rate
    
    # 4. Fallback to item standard rate if available
    if hasattr(item, 'standard_rate') and item.standard_rate:
        return item.standard_rate
    
    raise ValidationError(f"No price available for item {item.name}")


def get_item_prices_bulk(company, item_ids, party=None):
    """
    Get prices for multiple items at once.
    
    Args:
        company: Company instance
        item_ids: List of item IDs
        party: Party instance (optional)
    
    Returns:
        dict: {item_id: price}
    """
    items = StockItem.objects.filter(id__in=item_ids, company=company)
    prices = {}
    
    for item in items:
        try:
            prices[str(item.id)] = resolve_price(company, item, party)
        except ValidationError:
            prices[str(item.id)] = None
    
    return prices
