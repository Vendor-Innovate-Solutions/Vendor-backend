"""
Serializers for Products app.
Handles Product and Category catalog management for B2B portal.
"""
from rest_framework import serializers
from apps.products.models import Product, Category


class CategorySerializer(serializers.ModelSerializer):
    """
    Serializer for Product Category.
    UUID-based primary key for multi-tenant safety.
    """
    id = serializers.UUIDField(read_only=True)
    company_id = serializers.UUIDField(read_only=True)
    product_count = serializers.IntegerField(read_only=True, required=False)
    
    class Meta:
        model = Category
        fields = [
            'id',
            'company_id',
            'name',
            'description',
            'is_active',
            'display_order',
            'product_count',
            'created_at',
            'updated_at'
        ]
        read_only_fields = ['id', 'company_id', 'created_at', 'updated_at']


class ProductListSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for product listing.
    Optimized for catalog browsing.
    """
    id = serializers.UUIDField(read_only=True)
    company_id = serializers.UUIDField(read_only=True)
    category_id = serializers.UUIDField(required=False, allow_null=True)
    category_name = serializers.CharField(source='category.name', read_only=True)
    
    class Meta:
        model = Product
        fields = [
            'id',
            'company_id',
            'name',
            'category_id',
            'category_name',
            'brand',
            'available_quantity',
            'unit',
            'price',
            'status',
            'is_portal_visible',
            'is_featured',
            'created_at'
        ]
        read_only_fields = ['id', 'company_id', 'category_name', 'created_at']


class ProductDetailSerializer(serializers.ModelSerializer):
    """
    Detailed serializer for product CRUD operations.
    Includes all fields and tax information.
    """
    id = serializers.UUIDField(read_only=True)
    company_id = serializers.UUIDField(read_only=True)
    category_id = serializers.UUIDField(required=False, allow_null=True)
    category_name = serializers.CharField(source='category.name', read_only=True)
    created_by_id = serializers.UUIDField(required=False, allow_null=True)
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    
    # Stock item count (reverse relation)
    stock_item_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Product
        fields = [
            'id',
            'company_id',
            'name',
            'category_id',
            'category_name',
            'description',
            'brand',
            'available_quantity',
            'unit',
            'total_shipped',
            'total_required_quantity',
            'price',
            'hsn_code',
            'cgst_rate',
            'sgst_rate',
            'igst_rate',
            'cess_rate',
            'is_portal_visible',
            'is_featured',
            'status',
            'created_by_id',
            'created_by_name',
            'stock_item_count',
            'created_at',
            'updated_at'
        ]
        read_only_fields = [
            'id',
            'company_id',
            'category_name',
            'created_by_name',
            'stock_item_count',
            'created_at',
            'updated_at'
        ]
    
    def get_stock_item_count(self, obj):
        """Count linked stock items."""
        return obj.stockitems.count()
    
    def validate_category_id(self, value):
        """Ensure category belongs to the same company."""
        if value:
            request = self.context.get('request')
            if request and request.company:
                try:
                    category = Category.objects.get(id=value, company=request.company)
                except Category.DoesNotExist:
                    raise serializers.ValidationError(
                        "Category not found or doesn't belong to your company."
                    )
        return value


class ProductCreateUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating/updating products.
    Excludes read-only aggregated fields.
    """
    id = serializers.UUIDField(read_only=True)
    category_id = serializers.UUIDField(required=False, allow_null=True)
    
    class Meta:
        model = Product
        fields = [
            'id',
            'name',
            'category_id',
            'description',
            'brand',
            'unit',
            'price',
            'available_quantity',
            'total_shipped',
            'total_required_quantity',
            'hsn_code',
            'cgst_rate',
            'sgst_rate',
            'igst_rate',
            'cess_rate',
            'is_portal_visible',
            'is_featured',
            'status'
        ]
        read_only_fields = ['id']
    
    def validate_category_id(self, value):
        """Ensure category belongs to the same company."""
        if value:
            request = self.context.get('request')
            if request and hasattr(request, 'company'):
                try:
                    Category.objects.get(id=value, company=request.company)
                except Category.DoesNotExist:
                    raise serializers.ValidationError(
                        "Category not found or doesn't belong to your company."
                    )
        return value
    
    def create(self, validated_data):
        """Create product with company context."""
        request = self.context.get('request')
        if not request or not request.company:
            raise serializers.ValidationError(
                "No active company found. Please ensure you have a company assigned."
            )
        
        validated_data['company'] = request.company
        validated_data['created_by'] = request.user
        
        # Handle category_id -> category conversion
        category_id = validated_data.pop('category_id', None)
        if category_id:
            validated_data['category'] = Category.objects.get(id=category_id)
        
        return super().create(validated_data)
    
    def update(self, instance, validated_data):
        """Update product, handling category FK."""
        category_id = validated_data.pop('category_id', None)
        if category_id:
            validated_data['category'] = Category.objects.get(id=category_id)
        elif 'category_id' in self.initial_data and not category_id:
            # Explicit null
            validated_data['category'] = None
        
        return super().update(instance, validated_data)
