"""
Middleware to ensure DRF Response objects are rendered before
reaching Django's CommonMiddleware.

This fixes the ContentNotRenderedError that occurs when CommonMiddleware
tries to access response.content before DRF has rendered the response.
"""
from django.utils.deprecation import MiddlewareMixin


class DRFResponseMiddleware(MiddlewareMixin):
    """
    Middleware that ensures DRF Response objects are properly rendered.
    
    Place at the END of MIDDLEWARE list (runs first in response phase).
    """
    
    def process_response(self, request, response):
        """
        Render DRF Response objects if they haven't been rendered yet.
        """
        print(f">>> DRFResponseMiddleware processing: {request.path}")
        print(f">>> Response type: {type(response)}")
        print(f">>> Has render: {hasattr(response, 'render')}")
        
        # Check if this is a TemplateResponse that needs rendering
        if hasattr(response, 'render') and callable(response.render):
            is_rendered = getattr(response, 'is_rendered', True)
            print(f">>> Is rendered: {is_rendered}")
            
            if not is_rendered:
                try:
                    print(">>> Rendering response...")
                    response = response.render()
                    print(">>> Response rendered successfully")
                except Exception as e:
                    # If rendering fails, return a basic error response
                    from django.http import JsonResponse
                    import traceback
                    print(f">>> DRF Response rendering error: {e}")
                    print(traceback.format_exc())
                    return JsonResponse(
                        {
                            'error': 'Response rendering failed',
                            'detail': str(e)
                        },
                        status=500
                    )
        
        return response
