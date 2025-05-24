from flask import Flask, request, jsonify
import requests
import xml.etree.ElementTree as ET

app = Flask(__name__)

# Configure CORS to allow requests from the frontend (prototype.html)
# For development, allowing all origins is fine. For production, restrict this.
from flask_cors import CORS
CORS(app)

def extract_pmid_from_url(url_or_id):
    # Basic regex to extract PubMed ID from various URL formats or if it's just an ID
    # Handles URLs like:
    # https://pubmed.ncbi.nlm.nih.gov/38832098/
    # https://www.ncbi.nlm.nih.gov/pubmed/38832098
    # and plain IDs like "38832098"
    import re
    match = re.search(r"(?:pubmed\.ncbi\.nlm\.nih\.gov\/|www\.ncbi\.nlm\.nih\.gov\/pubmed\/|^\s*)(\d+)", url_or_id)
    return match.group(1) if match else None

@app.route('/api/fetch-pubmed-abstract', methods=['GET'])
def fetch_pubmed_abstract_route():
    pubmed_input = request.args.get('pubmedIdOrUrl')
    if not pubmed_input:
        return jsonify({"error": "Missing pubmedIdOrUrl parameter"}), 400

    pmid = extract_pmid_from_url(pubmed_input)
    if not pmid:
        return jsonify({"error": "Invalid PubMed ID or URL format"}), 400

    try:
        # NCBI E-utilities API endpoint for fetching PubMed abstracts
        eutils_url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pubmed&id={pmid}&retmode=xml&rettype=abstract"
        
        response = requests.get(eutils_url, timeout=10) # Added timeout
        response.raise_for_status()  # Raise an exception for HTTP errors (4xx or 5xx)

        xml_data = response.text
        root = ET.fromstring(xml_data)

        # Find the ArticleTitle and AbstractText elements
        # Note: XML structure can vary, this is a common path.
        article_title_element = root.find('.//ArticleTitle')
        abstract_text_element = root.find('.//AbstractText') # Handles <AbstractText Label="..."> and simple <AbstractText>

        # Fallback if AbstractText is not found, try to find NlmCategory AbstractText
        if abstract_text_element is None:
            abstract_text_element = root.find('.//Abstract/AbstractText')


        title = article_title_element.text if article_title_element is not None else "Title not found"
        
        abstract_parts = []
        if abstract_text_element is not None:
            # Handles cases where AbstractText might have sub-elements or be segmented
            if abstract_text_element.text: # Main text of the element
                 abstract_parts.append(abstract_text_element.text.strip())
            for sub_element in abstract_text_element: # Iterate over child elements like <i/>, <b/>, etc.
                if sub_element.text:
                    abstract_parts.append(sub_element.text.strip())
                if sub_element.tail: # Text after a child element
                    abstract_parts.append(sub_element.tail.strip())
            abstract = " ".join(filter(None, abstract_parts)) if abstract_parts else "Abstract not found"
        else:
            abstract = "Abstract not found"
            
        # Check for common error messages within the XML if parsing seems to fail
        if title == "Title not found" and abstract == "Abstract not found":
            error_elements = root.findall('.//ERROR')
            if error_elements:
                error_message = "; ".join([err.text for err in error_elements if err.text])
                return jsonify({"error": f"NCBI API Error: {error_message}", "pmid": pmid}), 500


        return jsonify({
            "pmid": pmid,
            "title": title,
            "abstract": abstract
        })

    except requests.exceptions.RequestException as e:
        return jsonify({"error": f"Failed to connect to NCBI E-utilities: {str(e)}", "pmid": pmid}), 500
    except ET.ParseError:
        return jsonify({"error": "Failed to parse XML response from NCBI", "pmid": pmid}), 500
    except Exception as e:
        return jsonify({"error": f"An unexpected error occurred: {str(e)}", "pmid": pmid}), 500

if __name__ == '__main__':
    # Runs on http://127.0.0.1:5000/ by default
    app.run(debug=True) 