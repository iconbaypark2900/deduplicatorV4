import { useState, useEffect, useRef } from 'react';
import { getAbsoluteApiUrl } from '../../services/baseApi';

interface DirectImageDisplayProps {
  pageNumber: number;
  alt: string;
  className?: string;
}

export default function DirectImageDisplay({ pageNumber, alt, className = "w-full h-full object-contain" }: DirectImageDisplayProps) {
  const [loading, setLoading] = useState(true);
  const [imageUrl, setImageUrl] = useState<string | null>(null);
  const [error, setError] = useState(false);
  const imageLoadAttempted = useRef(false);
  
  useEffect(() => {
    // Reset states when page number changes
    setLoading(true);
    setImageUrl(null);
    setError(false);
    imageLoadAttempted.current = false;
    
    // Direct access using static mapping - most efficient approach
    const knownImageHashes: Record<number, string[]> = {
      1: ["16936dd2", "f84dd164", "5ee62f21", "93bea304", "76dba2e7", "4d5663dc", "e4adc626", "87b6da2f", "ec7abc48"],
      2: ["34837728", "faf8fd1b", "c657a9c5", "536238e4", "b4355944", "a1a60d2c", "dc58a5ce", "a01a3d7f", "98847e9e"],
      3: ["948b3e22", "5e251c42", "fbd92b1c", "612744bf", "5cc46a71", "a0f6d27a", "0f39404d", "dd50392b", "69c5e488"],
      4: ["09689d6e", "09b73e5b", "0ab77969", "a8968bab", "cbb7f0df", "ef0e9998", "cf2ffee2", "3a27d765", "3795bf42"],
      5: ["dbdd3930", "fcddad95", "41ad0362", "834ccfd3", "2e572055", "f677d004", "ab1cabd8", "429aa5a8", "33bfe62b"]
    };
    
    // Function to try to load an image from a URL and set it if successful
    const tryLoadImage = (url: string): Promise<boolean> => {
      return new Promise((resolve) => {
        const img = new Image();
        img.onload = () => {
          setImageUrl(url);
          setLoading(false);
          resolve(true);
        };
        img.onerror = () => resolve(false);
        img.src = getAbsoluteApiUrl(url);
      });
    };
    
    // Try all our image loading strategies in sequence
    const loadImage = async () => {
      try {
        // If we've already tried to load this image, don't try again
        if (imageLoadAttempted.current) return;
        imageLoadAttempted.current = true;
        
        // 1. Try known hashes for this page (direct client-side lookup)
        if (knownImageHashes[pageNumber] && knownImageHashes[pageNumber].length > 0) {
          for (const hash of knownImageHashes[pageNumber]) {
            const url = `/temp/page${pageNumber}_${hash}.png`;
            if (await tryLoadImage(url)) {
              return;
            }
          }
        }
        
        // 2. Try direct endpoints if client-side lookup failed
        try {
          // Try the new direct page number endpoint
          const directUrl = `/page/number/${pageNumber}/image`;
          if (await tryLoadImage(directUrl)) {
            return;
          }
          
          // Try the legacy page endpoint
          const legacyUrl = `/page/${pageNumber}/image`;
          if (await tryLoadImage(legacyUrl)) {
            return;
          }
        } catch (err) {
          console.log("Failed to use direct endpoints");
        }
        
        // 3. As a last resort, try to fetch the debug endpoint to get available images
        try {
          const response = await fetch(getAbsoluteApiUrl('/debug/available-images'));
          if (response.ok) {
            const data = await response.json();
            const matchingImages = data.images.filter((img: any) => 
              img.filename.startsWith(`page${pageNumber}_`)
            );
            
            if (matchingImages.length > 0) {
              // Try each matching image
              for (const img of matchingImages) {
                if (await tryLoadImage(img.url)) {
                  return;
                }
              }
            }
          }
        } catch (err) {
          console.log("Failed to use debug endpoint");
        }
        
        // 4. If all approaches failed, show error
        setError(true);
        setLoading(false);
      } catch (error) {
        console.error("Error in image loading process:", error);
        setError(true);
        setLoading(false);
      }
    };
    
    loadImage();
  }, [pageNumber]);
  
  // Render loading state, image, or fallback
  if (loading) {
    return (
      <div className="flex items-center justify-center w-full h-full">
        <div className="text-white text-opacity-70 text-sm">
          <div className="w-5 h-5 border-t-2 border-blue-500 rounded-full animate-spin mx-auto mb-2"></div>
          Loading page {pageNumber}...
        </div>
      </div>
    );
  }
  
  if (imageUrl) {
    return (
      <img 
        src={getAbsoluteApiUrl(imageUrl)}
        alt={alt}
        className={className}
        onError={(e) => {
          console.error(`Failed to load image: ${imageUrl}`);
          e.currentTarget.style.display = 'none';
          e.currentTarget.parentElement!.innerHTML = 
            `<div class="p-4 text-center text-gray-400">Error loading page ${pageNumber}</div>`;
        }}
      />
    );
  }
  
  return (
    <div className="flex items-center justify-center w-full h-full">
      <div className="text-gray-400 text-center">
        <svg xmlns="http://www.w3.org/2000/svg" className="h-10 w-10 mx-auto mb-2 text-gray-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
        </svg>
        <div>Image unavailable for page {pageNumber}</div>
      </div>
    </div>
  );
} 