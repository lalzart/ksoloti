package axoloti.mcp;

/**
 * Interface for language model services used to process natural language
 * and generate patch specifications
 */
public interface LLMService {
    
    /**
     * Generate a JSON patch specification from a natural language description
     * 
     * @param description The natural language description
     * @return A JSON string containing the patch specification
     */
    String generatePatchSpecification(String description);
    
} 